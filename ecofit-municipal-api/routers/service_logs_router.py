from fastapi import APIRouter, Query, HTTPException
from database import database
from datetime import datetime, timedelta, timezone
from bson import ObjectId

from services.prediction_trigger import prediction_trigger
from services.ward_features_builder import rebuild_recent_ward_hourly_features

router = APIRouter(prefix="/api/v1/service-logs", tags=["Service Logs"])

col = database.get_collection("service_logs")


def to_json(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    return doc


# ---------------- GET LIVE ----------------
@router.get("/live")
async def get_live_service_logs(hours: int = Query(24, ge=1, le=168)):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    cursor = col.find({"createdAt": {"$gte": since}}).sort("createdAt", -1).limit(500)

    data = []
    async for doc in cursor:
        data.append(to_json(doc))

    return data


# ---------------- CREATE ----------------
@router.post("")
async def create_service_log(payload: dict):

    now = datetime.now(timezone.utc)

    payload.setdefault("createdAt", now)
    payload.setdefault("updatedAt", now)

    required = ["serviceType", "shift", "startTime", "endTime", "outcome", "volumeLevel"]
    missing = [k for k in required if k not in payload]

    if missing:
        raise HTTPException(status_code=400, detail=f"Missing fields: {missing}")

    result = await col.insert_one(payload)

    doc = await col.find_one({"_id": result.inserted_id})

    try:

        # ✅ rebuild live hourly features
        await rebuild_recent_ward_hourly_features()

        # ✅ run prediction
        await prediction_trigger.trigger()

    except Exception as e:
        print("Prediction trigger failed:", repr(e))

    return to_json(doc)


# ---------------- UPDATE ----------------
@router.patch("/{log_id}")
async def patch_service_log(log_id: str, payload: dict):

    try:
        object_id = ObjectId(log_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid log ID")

    payload["updatedAt"] = datetime.now(timezone.utc)

    result = await col.update_one({"_id": object_id}, {"$set": payload})

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Service log not found")

    updated_doc = await col.find_one({"_id": object_id})

    try:

        # ✅ rebuild features
        await rebuild_recent_ward_hourly_features()

        # ✅ run prediction
        await prediction_trigger.trigger()

    except Exception as e:
        print("Prediction trigger failed:", repr(e))

    return to_json(updated_doc)


# ---------------- DELETE ----------------
@router.delete("/{log_id}")
async def delete_service_log(log_id: str):

    try:
        object_id = ObjectId(log_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid log ID")

    result = await col.delete_one({"_id": object_id})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Service log not found")

    try:

        # ✅ rebuild features
        await rebuild_recent_ward_hourly_features()

        # ✅ run prediction
        await prediction_trigger.trigger()

    except Exception as e:
        print("Prediction trigger failed:", repr(e))

    return {"message": "Deleted successfully"}