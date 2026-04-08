from typing import Optional, List, Any
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field
from bson import ObjectId

from database import database

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])

ALERTS_COL = "alerts"


def iso(dt: Any) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class CreateAlertRequest(BaseModel):
    wardId: str
    wardName: Optional[str] = None
    riskClass: str
    riskScore: float
    tsPrediction: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    title: Optional[str] = None
    description: Optional[str] = None


class AlertItem(BaseModel):
    id: str = Field(..., alias="_id")
    wardId: str
    wardName: Optional[str] = None
    riskClass: str
    riskScore: float
    tsPrediction: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    title: Optional[str] = None
    description: Optional[str] = None
    status: str
    createdAt: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/health")
def health():
    return {"status": "alerts router ok", "ts": datetime.utcnow().isoformat()}


@router.post("/create", response_model=AlertItem)
async def create_alert(payload: CreateAlertRequest):
    doc = {
        "wardId": payload.wardId,
        "wardName": payload.wardName,
        "riskClass": payload.riskClass,
        "riskScore": float(payload.riskScore),
        "tsPrediction": payload.tsPrediction,
        "lat": payload.lat,
        "lng": payload.lng,
        "title": payload.title or f"Risk Alert: {payload.riskClass}",
        "description": payload.description
        or f"Ward {payload.wardId} flagged as {payload.riskClass} (score={float(payload.riskScore):.3f}).",
        "status": "OPEN",
        "createdAt": datetime.utcnow(),
    }

    res = await database[ALERTS_COL].insert_one(doc)
    doc["_id"] = str(res.inserted_id)
    doc["createdAt"] = iso(doc["createdAt"])
    return doc


@router.get("/latest", response_model=List[AlertItem])
async def latest(limit: int = 50):
    limit = max(1, min(int(limit), 500))
    cursor = database[ALERTS_COL].find({}, sort=[("createdAt", -1)]).limit(limit)

    out = []
    async for d in cursor:
        d["_id"] = str(d["_id"])
        d["createdAt"] = iso(d.get("createdAt"))
        out.append(d)
    return out


@router.post("/close/{alert_id}")
async def close_alert(alert_id: str):
    res = await database[ALERTS_COL].update_one(
        {"_id": ObjectId(alert_id)},
        {"$set": {"status": "CLOSED", "closedAt": datetime.utcnow()}},
    )
    if res.matched_count == 0:
        return {"ok": False, "message": "alert not found"}
    return {"ok": True, "message": "closed"}