from fastapi import APIRouter, Query
from typing import Dict, Any, List
from datetime import datetime, timedelta
from database import database

router = APIRouter(prefix="/api/v1/ward-hourly-features", tags=["Ward Hourly Features"])

COLLECTION = "ward_hourly_features"


def json_safe(doc: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in doc.items():
        if k == "_id":
            out["id"] = str(v)  # optional
            continue
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


@router.get("")
async def get_ward_hourly_features(
    wardId: str,
    hours: int = Query(default=48, ge=1, le=168),
):
    coll = database[COLLECTION]

    # ✅ Get latest N hourly records for ward (does not depend on current date)
    cursor = (
        coll.find({"wardId": wardId})
        .sort("tsHour", -1)
        .limit(hours)
    )

    items: List[Dict[str, Any]] = []
    async for doc in cursor:
        items.append(json_safe(doc))

    # ✅ Return in ascending order (old -> new) for UI
    items = list(reversed(items))

    return {"wardId": wardId, "hours": hours, "count": len(items), "items": items}