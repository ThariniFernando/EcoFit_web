import os
import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field
from pymongo import MongoClient, DESCENDING
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/api/v1/dispatch", tags=["dispatch"])

MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = os.getenv("DB_NAME", "ecofit_db")

PREDICTIONS_COL = os.getenv("PREDICTIONS_COL", "predictions_hourly")
WARDS_MASTER_COL = os.getenv("WARDS_MASTER_COL", "wards_master")
DISPATCH_PLANS_COL = os.getenv("DISPATCH_PLANS_COL", "dispatch_plans")


# ---------------------------
# DB helper
# ---------------------------
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


# ---------------------------
# Simple geo helpers
# ---------------------------
def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    # (lat, lng) in degrees
    lat1, lon1 = a
    lat2, lon2 = b
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    x = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(x))


def greedy_route(points: List[Dict[str, Any]], start: Tuple[float, float]) -> List[Dict[str, Any]]:
    # nearest-neighbor route (fast + good enough for demo)
    remaining = points[:]
    curr = start
    route = []
    while remaining:
        best_i = 0
        best_d = float("inf")
        for i, p in enumerate(remaining):
            d = haversine_km(curr, (p["lat"], p["lng"]))
            if d < best_d:
                best_d = d
                best_i = i
        nxt = remaining.pop(best_i)
        nxt["distanceFromPrevKm"] = round(best_d, 3)
        route.append(nxt)
        curr = (nxt["lat"], nxt["lng"])
    return route


# ---------------------------
# Request/Response models
# ---------------------------
class BulkPlanRequest(BaseModel):
    # which set to plan
    mode: str = Field(default="EMERGENCY", description="EMERGENCY | HIGH_PLUS | ALL")
    topN: int = Field(default=10, ge=1, le=200)
    # optional: if you want only a ward list from UI
    wardIds: Optional[List[str]] = None

    # optional starting point (municipality yard/garage)
    startLat: float = 6.9271
    startLng: float = 79.8612


class WardPlanItem(BaseModel):
    wardId: str
    wardName: Optional[str] = None
    lat: float
    lng: float
    riskClass: str
    riskScore: float
    tsPrediction: Optional[str] = None


class BulkPlanResponse(BaseModel):
    tsPrediction: Optional[str]
    mode: str
    selectedCount: int
    resources: Dict[str, Any]
    route: List[Dict[str, Any]]
    actionSteps: List[str]
    savedPlanId: Optional[str] = None


# ---------------------------
# Core: read latest prediction batch + join ward centers
# ---------------------------
def fetch_latest_batch_joined(limit: int = 5000) -> Tuple[Optional[datetime], List[Dict[str, Any]]]:
    db = get_db()

    latest_doc = db[PREDICTIONS_COL].find_one({}, sort=[("tsPrediction", DESCENDING)])
    if not latest_doc or not latest_doc.get("tsPrediction"):
        return None, []

    ts_pred = latest_doc["tsPrediction"]

    wards = list(
        db[WARDS_MASTER_COL].find(
            {"active": True},
            projection={"_id": 0, "wardId": 1, "wardName": 1, "center": 1},
        )
    )
    ward_map: Dict[str, Dict[str, Any]] = {}
    for w in wards:
        wid = (w.get("wardId") or "").strip()
        if not wid:
            continue
        center = w.get("center") or {}
        lat = center.get("lat")
        lng = center.get("lng")
        ward_map[wid] = {"wardName": w.get("wardName"), "lat": lat, "lng": lng}

    pred_docs = list(
        db[PREDICTIONS_COL].find(
            {"tsPrediction": ts_pred},
            projection={
                "_id": 1,
                "wardId": 1,
                "tsPrediction": 1,
                "riskClass": 1,
                "riskScore": 1,
                "probabilities": 1,
            },
        ).limit(limit)
    )

    items: List[Dict[str, Any]] = []
    for p in pred_docs:
        wid = (p.get("wardId") or "").strip()
        wm = ward_map.get(wid, {})
        lat = wm.get("lat")
        lng = wm.get("lng")

        # skip if no coordinates
        if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
            continue

        items.append(
            {
                "_id": str(p.get("_id")),
                "wardId": wid,
                "wardName": wm.get("wardName"),
                "lat": float(lat),
                "lng": float(lng),
                "tsPrediction": iso(p.get("tsPrediction")),
                "riskClass": str(p.get("riskClass") or ""),
                "riskScore": float(p.get("riskScore") or 0.0),
                "probabilities": list(p.get("probabilities") or []),
            }
        )

    return ts_pred, items


def build_resources(selected: List[Dict[str, Any]]) -> Dict[str, Any]:
    # simple demo resource logic
    # you can tune later (or replace by GNN output)
    em = sum(1 for x in selected if x["riskClass"] == "EMERGENCY")
    hi = sum(1 for x in selected if x["riskClass"] == "HIGH")
    med = sum(1 for x in selected if x["riskClass"] == "MEDIUM")
    low = sum(1 for x in selected if x["riskClass"] == "LOW")

    # rule-of-thumb
    trucks = max(1, math.ceil((em * 1.5 + hi * 1.0 + med * 0.6 + low * 0.3) / 4))
    crews = trucks  # 1 crew per truck for now
    supervisors = 1 if em >= 5 else 0

    return {
        "counts": {"EMERGENCY": em, "HIGH": hi, "MEDIUM": med, "LOW": low},
        "recommended": {
            "trucks": int(trucks),
            "crews": int(crews),
            "supervisors": int(supervisors),
            "notes": "Rule-based recommendation (will be replaced by GNN/optimization later).",
        },
    }


# ---------------------------
# Endpoints
# ---------------------------
@router.get("/health")
def health():
    return {"status": "dispatch router ok", "ts": datetime.utcnow().isoformat()}


@router.get("/emergency-queue")
def emergency_queue(limit: int = Query(20, ge=1, le=200)):
    """
    Fast endpoint for UI:
    returns latest batch EMERGENCY wards sorted by riskScore desc
    """
    ts_pred, items = fetch_latest_batch_joined(limit=5000)
    if not ts_pred:
        return {"tsPrediction": None, "items": []}

    em = [x for x in items if x["riskClass"] == "EMERGENCY"]
    em.sort(key=lambda x: x["riskScore"], reverse=True)
    return {"tsPrediction": iso(ts_pred), "items": em[:limit]}


@router.post("/plan", response_model=BulkPlanResponse)
def plan(req: BulkPlanRequest):
    ts_pred, items = fetch_latest_batch_joined(limit=5000)
    if not ts_pred:
        raise HTTPException(status_code=404, detail="No predictions found")

    mode = (req.mode or "EMERGENCY").upper().strip()

    if req.wardIds:
        chosen = [x for x in items if x["wardId"] in set(req.wardIds)]
    else:
        if mode == "EMERGENCY":
            chosen = [x for x in items if x["riskClass"] == "EMERGENCY"]
        elif mode == "HIGH_PLUS":
            chosen = [x for x in items if x["riskClass"] in ("HIGH", "EMERGENCY")]
        elif mode == "ALL":
            chosen = items
        else:
            raise HTTPException(status_code=400, detail="mode must be EMERGENCY | HIGH_PLUS | ALL")

    chosen.sort(key=lambda x: x["riskScore"], reverse=True)
    chosen = chosen[: req.topN]

    if not chosen:
        return BulkPlanResponse(
            tsPrediction=iso(ts_pred),
            mode=mode,
            selectedCount=0,
            resources=build_resources([]),
            route=[],
            actionSteps=["No wards selected for planning."],
            savedPlanId=None,
        )

    start = (float(req.startLat), float(req.startLng))
    route = greedy_route(
        [
            {
                "wardId": x["wardId"],
                "wardName": x.get("wardName"),
                "lat": x["lat"],
                "lng": x["lng"],
                "riskClass": x["riskClass"],
                "riskScore": x["riskScore"],
                "tsPrediction": x.get("tsPrediction"),
            }
            for x in chosen
        ],
        start=start,
    )

    resources = build_resources(chosen)

    steps = [
        f"Dispatch {resources['recommended']['trucks']} trucks with {resources['recommended']['crews']} crews.",
        "Visit wards in suggestedRoute order (nearest-neighbor demo).",
        "For EMERGENCY wards: prioritize immediate cleanup + temporary bins + quick patrol follow-up.",
        "Record trip outcomes into Service Logs after completion.",
    ]

    # save plan for history/audit
    db = get_db()
    doc = {
        "createdAt": datetime.utcnow(),
        "tsPrediction": ts_pred,
        "mode": mode,
        "topN": req.topN,
        "wardIds": [x["wardId"] for x in chosen],
        "start": {"lat": req.startLat, "lng": req.startLng},
        "resources": resources,
        "route": route,
        "actionSteps": steps,
    }
    ins = db[DISPATCH_PLANS_COL].insert_one(doc)

    return BulkPlanResponse(
        tsPrediction=iso(ts_pred),
        mode=mode,
        selectedCount=len(chosen),
        resources=resources,
        route=route,
        actionSteps=steps,
        savedPlanId=str(ins.inserted_id),
    )