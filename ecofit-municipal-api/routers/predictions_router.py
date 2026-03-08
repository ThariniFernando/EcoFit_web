# backend/routers/predictions_router.py
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from dotenv import load_dotenv
from pymongo import DESCENDING

from database import database

load_dotenv()

router = APIRouter(prefix="/api/v1/predictions", tags=["predictions"])

PREDICTIONS_COL = os.getenv("PREDICTIONS_COL", "predictions_hourly")
WARDS_MASTER_COL = os.getenv("WARDS_MASTER_COL", "wards_master")


def get_db():
    return database


def iso(dt: Any) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def parse_csv_list(s: Optional[str]) -> Optional[List[str]]:
    if not s:
        return None
    parts = [p.strip() for p in s.split(",") if p.strip()]
    return parts or None


@router.get("/health")
async def health():
    return {
        "status": "predictions router ok",
        "ts": datetime.utcnow().isoformat(),
        "collection": PREDICTIONS_COL,
    }


@router.get("/latest")
async def latest(
    limit: int = Query(1000, ge=1, le=5000),
    riskClass: Optional[str] = Query(None, description="Comma-separated list like EMERGENCY,HIGH (optional)"),
    activeOnly: bool = Query(True, description="Use only active wards for coordinates"),
):
    db = get_db()

    latest_doc = await db[PREDICTIONS_COL].find_one(
        filter={},
        sort=[("tsPrediction", DESCENDING)],
    )

    if not latest_doc:
        return {"tsPrediction": None, "counts": {"TOTAL": 0}, "items": []}

    ts_pred = latest_doc.get("tsPrediction")
    if not ts_pred:
        return {"tsPrediction": None, "counts": {"TOTAL": 0}, "items": []}

    ward_filter = {"active": True} if activeOnly else {}

    ward_map: Dict[str, Dict[str, Any]] = {}
    async for w in db[WARDS_MASTER_COL].find(
        ward_filter,
        projection={"_id": 0, "wardId": 1, "wardName": 1, "center": 1},
    ):
        wid = (w.get("wardId") or "").strip()
        if not wid:
            continue
        center = w.get("center") or {}
        ward_map[wid] = {
            "wardName": w.get("wardName"),
            "lat": center.get("lat"),
            "lng": center.get("lng"),
        }

    risk_list = parse_csv_list(riskClass)

    pred_filter: Dict[str, Any] = {"tsPrediction": ts_pred}
    if risk_list:
        pred_filter["riskClass"] = {"$in": risk_list}

    pred_docs: List[Dict[str, Any]] = []
    async for p in db[PREDICTIONS_COL].find(
        pred_filter,
        projection={
            "_id": 1,
            "wardId": 1,
            "tsPrediction": 1,
            "riskClass": 1,
            "riskScore": 1,
            "probabilities": 1,
        },
    ).limit(limit):
        pred_docs.append(p)

    counts_pipe = [
        {"$match": {"tsPrediction": ts_pred}},
        {"$group": {"_id": "$riskClass", "n": {"$sum": 1}}},
    ]

    counts_raw: List[Dict[str, Any]] = []
    async for r in db[PREDICTIONS_COL].aggregate(counts_pipe):
        counts_raw.append(r)

    counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "EMERGENCY": 0, "TOTAL": 0}
    for r in counts_raw:
        k = str(r.get("_id"))
        n = int(r.get("n") or 0)
        if k in counts:
            counts[k] = n
        counts["TOTAL"] += n

    items: List[Dict[str, Any]] = []
    for p in pred_docs:
        wid = (p.get("wardId") or "").strip()
        wm = ward_map.get(wid, {})

        items.append(
            {
                "_id": str(p.get("_id")),
                "wardId": wid,
                "wardName": wm.get("wardName"),
                "lat": wm.get("lat"),
                "lng": wm.get("lng"),
                "tsPrediction": iso(p.get("tsPrediction")),
                "riskClass": p.get("riskClass"),
                "riskScore": float(p.get("riskScore") or 0.0),
                "probabilities": list(p.get("probabilities") or []),
            }
        )

    return {"tsPrediction": iso(ts_pred), "counts": counts, "items": items}