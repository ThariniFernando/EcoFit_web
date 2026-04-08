from fastapi import APIRouter, Query
from typing import Dict, Any, List
from datetime import datetime, timedelta, timezone

from database import database

router = APIRouter(prefix="/api/v1/weather-hourly", tags=["Weather"])

COLLECTION = "weather_hourly"


def json_safe(doc: Dict[str, Any]):
    out = {}
    for k, v in doc.items():
        if k == "_id":
            continue
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


@router.get("")
async def get_weather(hours: int = Query(default=48, ge=1, le=168)):
    coll = database[COLLECTION]

    # FIX: timezone-aware datetime to match stored documents
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=hours)

    cursor = coll.find({"tsHour": {"$gte": start_time}}).sort("tsHour", 1)

    items: List[Dict[str, Any]] = []
    async for doc in cursor:
        items.append(json_safe(doc))

    return {"hours": hours, "count": len(items), "items": items}