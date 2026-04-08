import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field

from database import database

router = APIRouter(prefix="/api/v1/dispatch", tags=["dispatch"])

PREDICTIONS_COL = "predictions_hourly"
WARDS_MASTER_COL = "wards_master"
DISPATCH_PLANS_COL = "dispatch_plans"


def iso(dt: Any) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


# ---------------------------------------------------------------------------
# Geo helpers
# ---------------------------------------------------------------------------
def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
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
    remaining = points[:]
    curr = start
    route = []
    while remaining:
        best_i = min(
            range(len(remaining)),
            key=lambda i: haversine_km(curr, (remaining[i]["lat"], remaining[i]["lng"]))
        )
        nxt = remaining.pop(best_i)
        nxt["distanceFromPrevKm"] = round(haversine_km(curr, (nxt["lat"], nxt["lng"])), 3)
        route.append(nxt)
        curr = (nxt["lat"], nxt["lng"])
    return route


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class BulkPlanRequest(BaseModel):
    mode: str = Field(default="EMERGENCY", description="EMERGENCY | HIGH_PLUS | ALL")
    topN: int = Field(default=10, ge=1, le=200)
    wardIds: Optional[List[str]] = None
    startLat: float = 6.9271
    startLng: float = 79.8612


class BulkPlanResponse(BaseModel):
    tsPrediction: Optional[str]
    mode: str
    selectedCount: int
    resources: Dict[str, Any]
    route: List[Dict[str, Any]]
    actionSteps: List[str]
    savedPlanId: Optional[str] = None


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
async def fetch_latest_batch_joined(limit: int = 5000) -> Tuple[Optional[datetime], List[Dict[str, Any]]]:
    latest_doc = await database[PREDICTIONS_COL].find_one({}, sort=[("tsPrediction", -1)])
    if not latest_doc or not latest_doc.get("tsPrediction"):
        return None, []

    ts_pred = latest_doc["tsPrediction"]

    ward_map: Dict[str, Dict[str, Any]] = {}
    async for w in database[WARDS_MASTER_COL].find(
        {"active": True},
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

    items: List[Dict[str, Any]] = []
    async for p in database[PREDICTIONS_COL].find(
        {"tsPrediction": ts_pred},
        projection={"_id": 1, "wardId": 1, "tsPrediction": 1,
                    "riskClass": 1, "riskScore": 1, "probabilities": 1},
    ).limit(limit):
        wid = (p.get("wardId") or "").strip()
        wm = ward_map.get(wid, {})
        lat = wm.get("lat")
        lng = wm.get("lng")
        if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
            continue
        items.append({
            "_id": str(p.get("_id")),
            "wardId": wid,
            "wardName": wm.get("wardName"),
            "lat": float(lat),
            "lng": float(lng),
            "tsPrediction": iso(p.get("tsPrediction")),
            "riskClass": str(p.get("riskClass") or ""),
            "riskScore": float(p.get("riskScore") or 0.0),
            "probabilities": list(p.get("probabilities") or []),
        })

    return ts_pred, items


def build_resources(selected: List[Dict[str, Any]]) -> Dict[str, Any]:
    em  = sum(1 for x in selected if x["riskClass"] == "EMERGENCY")
    hi  = sum(1 for x in selected if x["riskClass"] == "HIGH")
    med = sum(1 for x in selected if x["riskClass"] == "MEDIUM")
    low = sum(1 for x in selected if x["riskClass"] == "LOW")
    trucks = max(1, math.ceil((em * 1.5 + hi * 1.0 + med * 0.6 + low * 0.3) / 4))
    return {
        "counts": {"EMERGENCY": em, "HIGH": hi, "MEDIUM": med, "LOW": low},
        "recommended": {
            "trucks": int(trucks),
            "crews": int(trucks),
            "supervisors": 1 if em >= 5 else 0,
            "notes": "Rule-based recommendation.",
        },
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("/health")
def health():
    return {"status": "dispatch router ok", "ts": datetime.utcnow().isoformat()}


@router.get("/emergency-queue")
async def emergency_queue(limit: int = Query(20, ge=1, le=200)):
    ts_pred, items = await fetch_latest_batch_joined(limit=5000)
    if not ts_pred:
        return {"tsPrediction": None, "items": []}
    em = sorted(
        [x for x in items if x["riskClass"] == "EMERGENCY"],
        key=lambda x: x["riskScore"],
        reverse=True,
    )
    return {"tsPrediction": iso(ts_pred), "items": em[:limit]}


@router.post("/plan", response_model=BulkPlanResponse)
async def plan(req: BulkPlanRequest):
    ts_pred, items = await fetch_latest_batch_joined(limit=5000)
    if not ts_pred:
        raise HTTPException(status_code=404, detail="No predictions found")

    mode = (req.mode or "EMERGENCY").upper().strip()

    if req.wardIds:
        chosen = [x for x in items if x["wardId"] in set(req.wardIds)]
    elif mode == "EMERGENCY":
        chosen = [x for x in items if x["riskClass"] == "EMERGENCY"]
    elif mode == "HIGH_PLUS":
        chosen = [x for x in items if x["riskClass"] in ("HIGH", "EMERGENCY")]
    elif mode == "ALL":
        chosen = items
    else:
        raise HTTPException(status_code=400, detail="mode must be EMERGENCY | HIGH_PLUS | ALL")

    chosen = sorted(chosen, key=lambda x: x["riskScore"], reverse=True)[: req.topN]

    if not chosen:
        return BulkPlanResponse(
            tsPrediction=iso(ts_pred), mode=mode, selectedCount=0,
            resources=build_resources([]), route=[],
            actionSteps=["No wards selected for planning."],
            savedPlanId=None,
        )

    start = (float(req.startLat), float(req.startLng))
    route = greedy_route(
        [{"wardId": x["wardId"], "wardName": x.get("wardName"),
          "lat": x["lat"], "lng": x["lng"], "riskClass": x["riskClass"],
          "riskScore": x["riskScore"], "tsPrediction": x.get("tsPrediction")}
         for x in chosen],
        start=start,
    )

    resources = build_resources(chosen)
    steps = [
        f"Dispatch {resources['recommended']['trucks']} trucks.",
        "Visit wards in suggestedRoute order (nearest-neighbor).",
        "For EMERGENCY wards: prioritize immediate cleanup.",
        "Record trip outcomes into Service Logs after completion.",
    ]

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
    ins = await database[DISPATCH_PLANS_COL].insert_one(doc)

    return BulkPlanResponse(
        tsPrediction=iso(ts_pred), mode=mode, selectedCount=len(chosen),
        resources=resources, route=route, actionSteps=steps,
        savedPlanId=str(ins.inserted_id),
    )