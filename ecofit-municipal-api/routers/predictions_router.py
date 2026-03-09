# backend/routers/predictions_router.py
import math
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
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


def safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_csv_list(s: Optional[str]) -> Optional[List[str]]:
    if not s:
        return None
    parts = [p.strip() for p in s.split(",") if p.strip()]
    return parts or None


def clean_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """
    Convert value to float and remove NaN / inf / -inf.
    """
    if value is None:
        return default

    try:
        f = float(value)
    except (TypeError, ValueError):
        return default

    if math.isnan(f) or math.isinf(f):
        return default

    return f


def clean_probabilities(value: Any) -> Any:
    """
    Keep probabilities JSON-safe.
    Supports dict or list. Anything invalid becomes safe values.
    """
    if value is None:
        return {}

    if isinstance(value, dict):
        cleaned = {}
        for k, v in value.items():
            if isinstance(v, (int, float)) or v is None:
                cleaned[k] = clean_float(v, 0.0)
            else:
                try:
                    cleaned[k] = clean_float(v, 0.0)
                except Exception:
                    cleaned[k] = 0.0
        return cleaned

    if isinstance(value, list):
        cleaned = []
        for v in value:
            cleaned.append(clean_float(v, 0.0))
        return cleaned

    return {}


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
    riskClass: Optional[str] = Query(
        None,
        description="Comma-separated list like EMERGENCY,HIGH (optional)",
    ),
    activeOnly: bool = Query(
        True,
        description="Use only active wards for coordinates",
    ),
):
    try:
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
            wid = safe_str(w.get("wardId"))
            if not wid:
                continue

            center = w.get("center") or {}
            if not isinstance(center, dict):
                center = {}

            ward_map[wid] = {
                "wardName": w.get("wardName"),
                "lat": clean_float(center.get("lat"), None),
                "lng": clean_float(center.get("lng"), None),
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
                "wardName": 1,
                "tsPrediction": 1,
                "riskClass": 1,
                "riskScore": 1,
                "probabilities": 1,
                "lat": 1,
                "lng": 1,
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
            wid = safe_str(p.get("wardId"))
            wm = ward_map.get(wid, {})

            item = {
                "_id": str(p.get("_id")),
                "wardId": wid,
                "wardName": p.get("wardName") or wm.get("wardName"),
                "lat": clean_float(
                    p.get("lat") if p.get("lat") is not None else wm.get("lat"),
                    None,
                ),
                "lng": clean_float(
                    p.get("lng") if p.get("lng") is not None else wm.get("lng"),
                    None,
                ),
                "tsPrediction": iso(p.get("tsPrediction")),
                "riskClass": p.get("riskClass"),
                "riskScore": clean_float(p.get("riskScore"), 0.0),
                "probabilities": clean_probabilities(p.get("probabilities")),
            }
            items.append(item)

        return {"tsPrediction": iso(ts_pred), "counts": counts, "items": items}

    except Exception as e:
        print("ERROR in /api/v1/predictions/latest:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))