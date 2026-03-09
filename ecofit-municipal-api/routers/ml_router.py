# backend/routers/ml_router.py
import os
import traceback
from datetime import datetime, timezone
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException

from database import database
from ml.inference import LSTMInference

load_dotenv()

router = APIRouter(prefix="/api/v1/ml", tags=["ML"])

PREDICTIONS_COL = os.getenv("PREDICTIONS_COL", "predictions_hourly")
WARDS_MASTER_COL = os.getenv("WARDS_MASTER_COL", "wards_master")


def norm_ward_id(x) -> str:
    return str(x or "").strip().upper()


def safe_float(value, default=None):
    try:
        if value is None:
            return default
        v = float(value)
        if v != v:  # nan
            return default
        if v == float("inf") or v == float("-inf"):
            return default
        return v
    except Exception:
        return default


@router.get("/health")
async def health():
    return {
        "status": "ml router ok",
        "ts": datetime.now(timezone.utc).isoformat(),
        "predictionsCollection": PREDICTIONS_COL,
        "wardsCollection": WARDS_MASTER_COL,
    }


async def run_predict_and_store() -> Dict[str, Any]:
    print("✅ run_predict_and_store started")

    infer = LSTMInference(database=database)
    preds = await infer.predict_all_wards()

    print(f"✅ predict_all_wards returned {len(preds)} items")

    if not preds:
        return {
            "tsPrediction": None,
            "items": [],
            "debug": {"total": 0, "missing_geo": 0},
            "collection": PREDICTIONS_COL,
        }

    ts_pred_dt = datetime.now(timezone.utc)

    ward_map = {}
    async for w in database[WARDS_MASTER_COL].find(
        {},
        projection={"_id": 0, "wardId": 1, "wardName": 1, "center": 1, "active": 1},
    ):
        wid = norm_ward_id(w.get("wardId"))
        center = w.get("center") or {}
        if not isinstance(center, dict):
            center = {}

        ward_map[wid] = {
            "wardName": w.get("wardName"),
            "lat": safe_float(center.get("lat"), None),
            "lng": safe_float(center.get("lng"), None),
            "active": w.get("active", True),
        }

    docs = []
    missing_geo = 0

    for p in preds:
        wid = norm_ward_id(p.get("wardId"))
        meta = ward_map.get(wid, {})

        lat = safe_float(meta.get("lat"), None)
        lng = safe_float(meta.get("lng"), None)

        if lat is None or lng is None:
            missing_geo += 1

        probs = p.get("probabilities", [])
        if isinstance(probs, list):
            clean_probs = [safe_float(x, 0.0) for x in probs]
        else:
            clean_probs = []

        risk_score = safe_float(p.get("riskScore", 0.0), 0.0)

        docs.append(
            {
                "wardId": wid,
                "wardName": meta.get("wardName"),
                "lat": lat,
                "lng": lng,
                "tsPrediction": ts_pred_dt,
                "riskClass": p.get("riskClass"),
                "riskScore": risk_score,
                "probabilities": clean_probs,
            }
        )

    print(f"✅ writing {len(docs)} docs to {PREDICTIONS_COL} at {ts_pred_dt.isoformat()}")

    if docs:
        await database[PREDICTIONS_COL].insert_many(docs)

    response_items = []
    for d in docs:
        response_items.append(
            {
                "wardId": d.get("wardId"),
                "wardName": d.get("wardName"),
                "lat": d.get("lat"),
                "lng": d.get("lng"),
                "tsPrediction": ts_pred_dt.isoformat(),
                "riskClass": d.get("riskClass"),
                "riskScore": d.get("riskScore"),
                "probabilities": d.get("probabilities", []),
            }
        )

    return {
        "tsPrediction": ts_pred_dt.isoformat(),
        "items": response_items,
        "debug": {"total": len(response_items), "missing_geo": missing_geo},
        "collection": PREDICTIONS_COL,
    }


@router.post("/predict-and-store")
async def predict_and_store():
    try:
        return await run_predict_and_store()
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "type": e.__class__.__name__,
            },
        )