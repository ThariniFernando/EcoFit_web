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


def normalize_status(value: Any) -> str:
    s = str(value or "").strip().upper()

    if s in ALLOWED_STATUSES:
        return s

    if s in {"OPEN", "PENDING"}:
        return "NEW"
    if s in {"INPROGRESS", "IN-PROGRESS"}:
        return "IN_PROGRESS"
    if s in {"DONE", "CLOSED"}:
        return "RESOLVED"

    return "NEW"


def extract_ward(doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ward = doc.get("ward") if isinstance(doc.get("ward"), dict) else {}

    ward_id = ward.get("wardId") or ward.get("id") or doc.get("wardId")
    ward_name = ward.get("wardName") or ward.get("name") or doc.get("wardName")
    ward_no = ward.get("wardNo") or ward.get("no")
    center = ward.get("center")

    if not ward_id and not ward_name and not ward_no and not center:
        return None

    return {
        "wardId": ward_id,
        "wardName": ward_name,
        "wardNo": ward_no,
        "center": center,
    }


def extract_location(doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    location = doc.get("location") if isinstance(doc.get("location"), dict) else {}

    if not location:
        return None

    address = location.get("address") or location.get("text")
    lat = location.get("lat")
    lng = location.get("lng")

    if (lat is None or lng is None) and isinstance(location.get("coordinates"), list):
        coords = location.get("coordinates") or []
        if len(coords) >= 2:
            lng = coords[0]
            lat = coords[1]

    if (lat is None or lng is None) and isinstance(location.get("geojson"), dict):
        geo = location.get("geojson") or {}
        coords = geo.get("coordinates") or []
        if len(coords) >= 2:
            lng = coords[0]
            lat = coords[1]

    if (lat is None or lng is None) and isinstance(location.get("type"), str):
        coords = location.get("coordinates") or []
        if len(coords) >= 2:
            lng = coords[0]
            lat = coords[1]

    known = {"address", "text", "lat", "lng", "type", "coordinates", "geojson"}
    extra = {k: v for k, v in location.items() if k not in known} or None

    if address is None and lat is None and lng is None and extra is None:
        return None

    return {
        "address": address,
        "lat": lat,
        "lng": lng,
        "extra": extra,
    }


def to_complaint_out(doc: Dict[str, Any]) -> Dict[str, Any]:
    ward = extract_ward(doc)
    location = extract_location(doc)

    out = {
        "id": str(doc["_id"]),
        "complaintId": doc.get("complaintId"),
        "source": doc.get("source"),
        "ward": ward,
        "location": location,
        "category": doc.get("category"),
        "severity": doc.get("severity"),
        "description": doc.get("description"),
        "status": normalize_status(doc.get("status")),
        "statusHistory": doc.get("statusHistory") if isinstance(doc.get("statusHistory"), list) else [],
        "assignedTo": doc.get("assignedTo"),
        "resolvedAt": doc.get("resolvedAt"),
        "resolution": doc.get("resolution"),
        "createdAt": doc.get("createdAt"),
        "updatedAt": doc.get("updatedAt"),
    }

    return json_safe(out)


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
        query["$or"] = [
            {"ward.wardId": wardId},
            {"wardId": wardId},
        ]

    if status:
        normalized = normalize_status(status)

        if normalized == "NEW":
            query["status"] = {"$in": ["NEW", "new", "OPEN", "open", "PENDING", "pending"]}
        elif normalized == "IN_PROGRESS":
            query["status"] = {"$in": ["IN_PROGRESS", "in_progress", "INPROGRESS", "inprogress"]}
        elif normalized == "RESOLVED":
            query["status"] = {"$in": ["RESOLVED", "resolved", "DONE", "done", "CLOSED", "closed"]}
        elif normalized == "REJECTED":
            query["status"] = {"$in": ["REJECTED", "rejected"]}

    if hours:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        query["createdAt"] = {"$gte": since}

    if q:
        q_filter = {
            "$or": [
                {"description": {"$regex": q, "$options": "i"}},
                {"category": {"$regex": q, "$options": "i"}},
                {"complaintId": {"$regex": q, "$options": "i"}},
                {"wardName": {"$regex": q, "$options": "i"}},
                {"ward.wardName": {"$regex": q, "$options": "i"}},
                {"wardId": {"$regex": q, "$options": "i"}},
                {"ward.wardId": {"$regex": q, "$options": "i"}},
            ]
        }

        if "$or" in query:
            existing_or = query["$or"]
            rest = {k: v for k, v in query.items() if k != "$or"}
            query = {
                "$and": [
                    {"$or": existing_or},
                    q_filter,
                    rest,
                ]
            }
        else:
            query.update(q_filter)

    sort_field = sort[1:] if sort.startswith("-") else sort
    sort_dir = -1 if sort.startswith("-") else 1

    total = await coll.count_documents(query)
    cursor = coll.find(query).sort(sort_field, sort_dir).skip(skip).limit(limit)

    items: List[Dict[str, Any]] = []
    async for doc in cursor:
        items.append(to_complaint_out(doc))

    return {"items": items, "total": total}


@router.get("/{id}")
async def get_complaint(id: str):
    coll = database[COLLECTION]
    doc = await coll.find_one({"_id": oid(id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return to_complaint_out(doc)


@router.patch("/{id}/status")
async def update_complaint_status(id: str, payload: Dict[str, Any]):
    coll = database[COLLECTION]
    now = datetime.now(timezone.utc)

    new_status = normalize_status(payload.get("status"))
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