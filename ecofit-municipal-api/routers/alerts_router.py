from typing import Optional, List, Dict, Any
from datetime import datetime
import os

from fastapi import APIRouter
from pydantic import BaseModel, Field
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])

MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = os.getenv("DB_NAME", "ecofit_db")

ALERTS_COL = os.getenv("ALERTS_COL", "alerts")


def get_db():
    if not MONGO_URL:
        raise RuntimeError("MONGO_URL missing in .env")
    client = MongoClient(MONGO_URL)
    return client[DB_NAME]


def iso(dt: Any) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


# -----------------------------
# Schemas
# -----------------------------
class CreateAlertRequest(BaseModel):
    wardId: str
    wardName: Optional[str] = None
    riskClass: str
    riskScore: float
    tsPrediction: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None

    # optional message fields
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


# -----------------------------
# Routes
# -----------------------------
@router.get("/health")
def health():
    return {"status": "alerts router ok", "ts": datetime.utcnow().isoformat()}


@router.post("/create", response_model=AlertItem)
def create_alert(payload: CreateAlertRequest):
    """
    Create an alert from a selected ward (usually EMERGENCY/HIGH).
    Stored in MongoDB alerts collection.
    """
    db = get_db()

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

    res = db[ALERTS_COL].insert_one(doc)
    doc["_id"] = str(res.inserted_id)
    doc["createdAt"] = iso(doc["createdAt"])
    return doc


@router.get("/latest", response_model=List[AlertItem])
def latest(limit: int = 50):
    """
    Returns most recent alerts.
    """
    db = get_db()
    cur = (
        db[ALERTS_COL]
        .find({}, sort=[("createdAt", -1)])
        .limit(max(1, min(int(limit), 500)))
    )

    out = []
    for d in cur:
        d["_id"] = str(d["_id"])
        d["createdAt"] = iso(d.get("createdAt"))
        out.append(d)
    return out


@router.post("/close/{alert_id}")
def close_alert(alert_id: str):
    """
    Mark alert as CLOSED.
    """
    db = get_db()
    res = db[ALERTS_COL].update_one(
        {"_id": __import__("bson").ObjectId(alert_id)},
        {"$set": {"status": "CLOSED", "closedAt": datetime.utcnow()}},
    )
    if res.matched_count == 0:
        return {"ok": False, "message": "alert not found"}
    return {"ok": True, "message": "closed"}