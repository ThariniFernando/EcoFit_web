from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from pymongo import ReturnDocument

from database import database
from services.prediction_trigger import prediction_trigger
from services.ward_features_builder import rebuild_recent_ward_hourly_features

router = APIRouter(prefix="/api/v1/complaints", tags=["Complaints"])

COLLECTION = "complaints"
ALLOWED_STATUSES = {"NEW", "IN_PROGRESS", "RESOLVED", "REJECTED"}


def oid(id: str) -> ObjectId:
    try:
        return ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")


def json_safe(v: Any):
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, list):
        return [json_safe(x) for x in v]
    if isinstance(v, dict):
        return {k: json_safe(x) for k, x in v.items()}
    return v


def to_complaint_out(doc: Dict[str, Any]) -> Dict[str, Any]:
    ward = doc.get("ward") if isinstance(doc.get("ward"), dict) else {}
    location = doc.get("location") if isinstance(doc.get("location"), dict) else {}

    loc_extra = None
    if location:
        known = {"address", "text", "lat", "lng"}
        loc_extra = {k: v for k, v in location.items() if k not in known} or None

    out = {
        "id": str(doc["_id"]),
        "complaintId": doc.get("complaintId"),
        "source": doc.get("source"),
        "ward": {
            "wardId": ward.get("wardId") or ward.get("id"),
            "wardName": ward.get("wardName") or ward.get("name"),
            "wardNo": ward.get("wardNo") or ward.get("no"),
            "center": ward.get("center"),
        } if ward else None,
        "location": {
            "address": location.get("address") or location.get("text"),
            "lat": location.get("lat"),
            "lng": location.get("lng"),
            "extra": loc_extra,
        } if location else None,
        "category": doc.get("category"),
        "severity": doc.get("severity"),
        "description": doc.get("description"),
        "status": doc.get("status", "NEW"),
        "statusHistory": doc.get("statusHistory") if isinstance(doc.get("statusHistory"), list) else [],
        "assignedTo": doc.get("assignedTo"),
        "resolvedAt": doc.get("resolvedAt"),
        "resolution": doc.get("resolution"),
        "createdAt": doc.get("createdAt"),
        "updatedAt": doc.get("updatedAt"),
    }

    return json_safe(out)


# ---------------- LIST ----------------
@router.get("")
async def list_complaints(
    wardId: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None, description="Search in description/category/complaintId"),
    hours: Optional[int] = Query(default=None, ge=1, le=168, description="Last N hours"),
    limit: int = Query(default=50, ge=1, le=200),
    skip: int = Query(default=0, ge=0),
    sort: str = Query(default="-createdAt", description="e.g. -createdAt or createdAt"),
):
    coll = database[COLLECTION]

    query: Dict[str, Any] = {}

    if wardId:
        query["ward.wardId"] = wardId

    if status:
        query["status"] = status

    if hours:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        query["createdAt"] = {"$gte": since}

    if q:
        query["$or"] = [
            {"description": {"$regex": q, "$options": "i"}},
            {"category": {"$regex": q, "$options": "i"}},
            {"complaintId": {"$regex": q, "$options": "i"}},
        ]

    sort_field = sort[1:] if sort.startswith("-") else sort
    sort_dir = -1 if sort.startswith("-") else 1

    total = await coll.count_documents(query)
    cursor = coll.find(query).sort(sort_field, sort_dir).skip(skip).limit(limit)

    items: List[Dict[str, Any]] = []
    async for doc in cursor:
        items.append(to_complaint_out(doc))

    return {"items": items, "total": total}


# ---------------- GET ONE ----------------
@router.get("/{id}")
async def get_complaint(id: str):
    coll = database[COLLECTION]
    doc = await coll.find_one({"_id": oid(id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return to_complaint_out(doc)


# ---------------- UPDATE STATUS ----------------
@router.patch("/{id}/status")
async def update_complaint_status(id: str, payload: Dict[str, Any]):
    coll = database[COLLECTION]
    now = datetime.now(timezone.utc)

    new_status = payload.get("status")
    if new_status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Allowed: {sorted(ALLOWED_STATUSES)}")

    history_item: Dict[str, Any] = {"status": new_status, "at": now}
    if payload.get("note"):
        history_item["note"] = payload["note"]

    update_doc: Dict[str, Any] = {
        "$set": {"status": new_status, "updatedAt": now},
        "$push": {"statusHistory": history_item},
    }

    if new_status == "RESOLVED":
        update_doc["$set"]["resolvedAt"] = now

    res = await coll.find_one_and_update(
        {"_id": oid(id)},
        update_doc,
        return_document=ReturnDocument.AFTER,
    )

    if not res:
        raise HTTPException(status_code=404, detail="Complaint not found")

    try:
        await rebuild_recent_ward_hourly_features()
        await prediction_trigger.trigger()
    except Exception as e:
        print("Prediction trigger failed:", repr(e))

    return to_complaint_out(res)