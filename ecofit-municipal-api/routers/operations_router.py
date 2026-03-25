# routers/operations_router.py
from __future__ import annotations

import os
from typing import List, Optional, Dict, Any, Tuple
from math import radians, sin, cos, asin, sqrt, ceil, floor
from datetime import datetime, timedelta, timezone

import requests
from fastapi import APIRouter
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from database import database

load_dotenv()

router = APIRouter(prefix="/api/v1/operations", tags=["operations"])

OSRM_BASE = "https://router.project-osrm.org"

SERVICE_LOGS_COL = os.getenv("SERVICE_LOGS_COL", "service_logs")
COMPLAINTS_COL = os.getenv("COMPLAINTS_COL", "complaints")


# -------------------------
# Utils
# -------------------------
def haversine_m(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    R = 6371000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    s = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * R * asin(sqrt(s))


def approx_travel_minutes(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    dist_m = haversine_m(a, b)
    return max(1.0, dist_m / 366.0)  # ~22 km/h fallback


def osrm_coords(points_latlng: List[Tuple[float, float]]) -> str:
    return ";".join([f"{lng:.6f},{lat:.6f}" for (lat, lng) in points_latlng])


def osrm_route(points_latlng: List[Tuple[float, float]]) -> Optional[Dict[str, Any]]:
    if len(points_latlng) < 2:
        return None

    coords = osrm_coords(points_latlng)
    url = f"{OSRM_BASE}/route/v1/driving/{coords}"
    params = {"overview": "full", "geometries": "geojson", "steps": "false"}

    try:
        r = requests.get(url, params=params, timeout=25)
        if not r.ok:
            return None

        data = r.json()
        routes = data.get("routes") or []
        if not routes:
            return None

        best = routes[0]
        geom = best.get("geometry")
        return {
            "geometry": geom,
            "distance_m": best.get("distance"),
            "duration_s": best.get("duration"),
        }
    except Exception:
        return None


def osrm_table(points_latlng: List[Tuple[float, float]]) -> Optional[Dict[str, Any]]:
    if len(points_latlng) < 2:
        return None

    coords = osrm_coords(points_latlng)
    url = f"{OSRM_BASE}/table/v1/driving/{coords}"
    params = {"annotations": "duration,distance"}

    try:
        r = requests.get(url, params=params, timeout=25)
        if not r.ok:
            return None
        return r.json()
    except Exception:
        return None


def extract_ward_id(doc: Dict[str, Any]) -> str:
    if doc.get("wardId"):
        return str(doc["wardId"]).strip()

    ward = doc.get("ward")
    if isinstance(ward, dict):
        for k in ["wardId", "id", "wardName", "name"]:
            if ward.get(k):
                return str(ward[k]).strip()

    if doc.get("wardName"):
        return str(doc["wardName"]).strip()

    return ""


def risk_class_weight(risk_class: str) -> float:
    rc = str(risk_class or "").upper().strip()
    if rc == "EMERGENCY":
        return 3.2
    if rc == "HIGH":
        return 1.7
    if rc == "MEDIUM":
        return 0.7
    return 0.0


# -------------------------
# Schemas
# -------------------------
class WardPoint(BaseModel):
    wardId: str
    wardName: Optional[str] = None
    lat: float
    lng: float
    riskClass: str
    riskScore: float


class GenerateActionPlanRequest(BaseModel):
    tsPrediction: str
    items: List[WardPoint] = Field(default_factory=list)

    crews: int = 3
    maxStopsPerCrew: int = 25
    trucksPerCrew: int = 1
    workersPerCrew: int = 2

    serviceMinutesPerStop: Optional[int] = 10

    depotLat: Optional[float] = None
    depotLng: Optional[float] = None
    depotName: Optional[str] = None


class RouteLeg(BaseModel):
    distanceM: Optional[float] = None
    durationS: Optional[float] = None
    mode: Optional[str] = None


class RouteStop(BaseModel):
    stopNo: int
    wardId: str
    wardName: Optional[str] = None
    lat: float
    lng: float
    riskClass: str
    riskScore: float
    priorityScore: Optional[float] = None
    boostReason: Optional[str] = None
    leg: Optional[RouteLeg] = None


class CrewPlan(BaseModel):
    crewNo: int
    depot: Dict[str, Any]
    stops: List[RouteStop] = Field(default_factory=list)
    polyline: Optional[List[List[float]]] = None

    trucksAllocated: int = 1
    workersAllocated: int = 2
    demandScore: float = 0.0


class ActionPlanResponse(BaseModel):
    tsPrediction: str
    strategy: str
    totalStops: int

    crews: int
    recommendedCrewCount: int
    recommendedTrucksPerCrew: int
    recommendedWorkersPerCrew: int

    crewPlans: List[CrewPlan]


# -------------------------
# Clustering / ordering
# -------------------------
def cluster_points(points: List[WardPoint], k: int) -> List[List[WardPoint]]:
    k = max(1, min(k, len(points)))

    try:
        from sklearn.cluster import KMeans  # type: ignore
        import numpy as np  # type: ignore

        X = np.array([[p.lat, p.lng] for p in points], dtype=float)
        km = KMeans(n_clusters=k, n_init=10, random_state=42)
        labels = km.fit_predict(X)

        clusters: List[List[WardPoint]] = [[] for _ in range(k)]
        for p, lab in zip(points, labels):
            clusters[int(lab)].append(p)

        clusters.sort(key=lambda c: len(c), reverse=True)
        return clusters
    except Exception:
        clusters = [[] for _ in range(k)]
        for i, p in enumerate(points):
            clusters[i % k].append(p)
        return clusters


def merge_tiny_clusters(
    clusters: List[List[WardPoint]],
    min_cluster_size: int = 3,
) -> List[List[WardPoint]]:
    """
    Merge clusters that are too small into the nearest larger cluster.
    Prevents wasteful crews with only 1–2 stops.
    """
    if len(clusters) <= 1:
        return clusters

    large = [c[:] for c in clusters if len(c) >= min_cluster_size]
    tiny = [c[:] for c in clusters if len(c) < min_cluster_size]

    if not tiny:
        return clusters

    if not large:
        # if all are tiny, just return original
        return clusters

    def cluster_center(cluster: List[WardPoint]) -> Tuple[float, float]:
        lat = sum(p.lat for p in cluster) / len(cluster)
        lng = sum(p.lng for p in cluster) / len(cluster)
        return lat, lng

    for small in tiny:
        s_center = cluster_center(small)

        best_i = 0
        best_dist = float("inf")
        for i, big in enumerate(large):
            b_center = cluster_center(big)
            d = haversine_m(s_center, b_center)
            if d < best_dist:
                best_dist = d
                best_i = i

        large[best_i].extend(small)

    large.sort(key=lambda c: len(c), reverse=True)
    return large


def order_priority_aware_nearest_neighbor(
    points: List[WardPoint],
    priority_map: Dict[str, float],
) -> List[WardPoint]:
    if not points:
        return []

    remaining = list(points)

    current = max(
        remaining,
        key=lambda x: priority_map.get(x.wardId, x.riskScore),
    )
    remaining.remove(current)
    ordered = [current]

    while remaining:
        last = ordered[-1]
        last_pos = (last.lat, last.lng)

        def candidate_score(p: WardPoint) -> float:
            priority = float(priority_map.get(p.wardId, p.riskScore))
            travel_min = approx_travel_minutes(last_pos, (p.lat, p.lng))
            class_bonus = risk_class_weight(p.riskClass)

            nearby_bonus = 0.0
            if travel_min <= 3:
                nearby_bonus = 1.8
            elif travel_min <= 6:
                nearby_bonus = 1.0
            elif travel_min <= 10:
                nearby_bonus = 0.35

            emergency_far_penalty = 0.0
            if str(p.riskClass).upper() == "EMERGENCY" and travel_min > 18:
                emergency_far_penalty = 0.8

            return (
                priority * 1.9
                + class_bonus
                + nearby_bonus
                - (travel_min * 0.22)
                - emergency_far_penalty
            )

        best = max(remaining, key=candidate_score)
        remaining.remove(best)
        ordered.append(best)

    return ordered


# -------------------------
# Recent operational signals
# -------------------------
async def get_recent_operational_signals(
    ward_ids: List[str],
    hours_back: int = 12,
) -> Dict[str, Dict[str, float]]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    ward_set = {w.strip() for w in ward_ids if w and w.strip()}

    signals: Dict[str, Dict[str, float]] = {
        w: {
            "missedCount": 0.0,
            "highMissedCount": 0.0,
            "complaintsCount": 0.0,
            "unresolvedComplaints": 0.0,
        }
        for w in ward_set
    }

    service_docs = await database[SERVICE_LOGS_COL].find(
        {"createdAt": {"$gte": since}},
        projection={
            "_id": 0,
            "wardId": 1,
            "ward": 1,
            "outcome": 1,
            "result": 1,
            "status": 1,
            "volumeLevel": 1,
        },
    ).to_list(length=None)

    for d in service_docs:
        wid = extract_ward_id(d)
        if wid not in signals:
            continue

        outcome = str(d.get("outcome") or d.get("result") or d.get("status") or "").upper().strip()
        volume = str(d.get("volumeLevel") or "").upper().strip()

        if "MISS" in outcome:
            signals[wid]["missedCount"] += 1.0
            if volume == "HIGH":
                signals[wid]["highMissedCount"] += 1.0

    complaint_docs = await database[COMPLAINTS_COL].find(
        {"createdAt": {"$gte": since}},
        projection={"_id": 0, "wardId": 1, "ward": 1, "status": 1},
    ).to_list(length=None)

    for d in complaint_docs:
        wid = extract_ward_id(d)
        if wid not in signals:
            continue

        status = str(d.get("status") or "").upper().strip()
        signals[wid]["complaintsCount"] += 1.0

        if status not in ["RESOLVED", "CLOSED", "REJECTED"]:
            signals[wid]["unresolvedComplaints"] += 1.0

    return signals


def make_priority_score(item: WardPoint, s: Dict[str, float]) -> Tuple[float, str]:
    missed = s.get("missedCount", 0.0)
    high_missed = s.get("highMissedCount", 0.0)
    complaints = s.get("complaintsCount", 0.0)
    unresolved = s.get("unresolvedComplaints", 0.0)

    class_boost = risk_class_weight(item.riskClass)

    boost = (
        class_boost
        + missed * 0.35
        + high_missed * 0.80
        + complaints * 0.12
        + unresolved * 0.22
    )

    priority = float(item.riskScore) + boost

    reasons = []
    if class_boost > 0:
        reasons.append(f"class:{item.riskClass}")
    if missed > 0:
        reasons.append(f"missed:{int(missed)}")
    if high_missed > 0:
        reasons.append(f"highMissed:{int(high_missed)}")
    if unresolved > 0:
        reasons.append(f"unresolved:{int(unresolved)}")
    if complaints > 0:
        reasons.append(f"complaints:{int(complaints)}")

    return priority, ", ".join(reasons) if reasons else "base-risk"


def recommend_resources(
    items: List[WardPoint],
    priority_map: Dict[str, float],
    signals_map: Dict[str, Dict[str, float]],
    req_crews: int,
    req_trucks: int,
    req_workers: int,
) -> Tuple[int, int, int]:
    """
    Practical rule:
    - keep crews useful
    - aim around 5–8 stops per crew
    - avoid too many crews with only 1–2 wards
    """
    total_priority = sum(priority_map.get(x.wardId, x.riskScore) for x in items)
    total_high_missed = sum(signals_map.get(x.wardId, {}).get("highMissedCount", 0.0) for x in items)
    total_missed = sum(signals_map.get(x.wardId, {}).get("missedCount", 0.0) for x in items)
    total_unresolved = sum(signals_map.get(x.wardId, {}).get("unresolvedComplaints", 0.0) for x in items)
    total_complaints = sum(signals_map.get(x.wardId, {}).get("complaintsCount", 0.0) for x in items)
    emergency_count = sum(1 for x in items if str(x.riskClass).upper() == "EMERGENCY")
    n = len(items)

    # base practical crew estimate from stop count
    crews_by_stop_load = ceil(n / 7)   # target about 7 stops per crew
    max_practical_crews = max(1, floor(n / 4))  # at least ~4 stops per crew
    min_practical_crews = max(1, ceil(n / 10))  # avoid under-allocation for large plans

    demand_pressure = 0
    if emergency_count >= 8:
        demand_pressure += 1
    if total_high_missed >= 6:
        demand_pressure += 1
    if total_unresolved >= 10:
        demand_pressure += 1
    if total_priority >= 120:
        demand_pressure += 1

    recommended_crews = crews_by_stop_load + demand_pressure

    recommended_crews = max(recommended_crews, min_practical_crews)
    recommended_crews = min(recommended_crews, max_practical_crews)

    # allow user minimum request but don't let it explode
    recommended_crews = max(min(req_crews, max_practical_crews), recommended_crews)

    recommended_trucks = max(
        req_trucks,
        2 if emergency_count >= 3 or total_high_missed >= 3 or total_missed >= 6 else 1,
    )

    recommended_workers = max(
        req_workers,
        5 if emergency_count >= 4 or total_unresolved >= 8 else
        4 if emergency_count >= 2 or total_high_missed >= 2 or total_complaints >= 6 else
        3 if total_complaints >= 3 or total_missed >= 3 else
        2,
    )

    return recommended_crews, recommended_trucks, recommended_workers


# -------------------------
# Endpoint
# -------------------------
@router.get("/health")
def health():
    return {"status": "operations router ok"}


@router.post("/action-plan", response_model=ActionPlanResponse)
async def action_plan(req: GenerateActionPlanRequest):
    depot = {
        "name": req.depotName or "Depot (Town Hall)",
        "lat": float(req.depotLat if req.depotLat is not None else 6.9271),
        "lng": float(req.depotLng if req.depotLng is not None else 79.8612),
    }

    items = [x for x in req.items if isinstance(x.lat, (int, float)) and isinstance(x.lng, (int, float))]
    if not items:
        return ActionPlanResponse(
            tsPrediction=req.tsPrediction,
            strategy="empty",
            totalStops=0,
            crews=req.crews,
            recommendedCrewCount=req.crews,
            recommendedTrucksPerCrew=req.trucksPerCrew,
            recommendedWorkersPerCrew=req.workersPerCrew,
            crewPlans=[],
        )

    ward_ids = [x.wardId for x in items]
    signals_map = await get_recent_operational_signals(ward_ids, hours_back=12)

    priority_map: Dict[str, float] = {}
    reason_map: Dict[str, str] = {}

    for x in items:
        priority, reason = make_priority_score(
            item=x,
            s=signals_map.get(x.wardId, {}),
        )
        priority_map[x.wardId] = priority
        reason_map[x.wardId] = reason

    recommended_crews, recommended_trucks, recommended_workers = recommend_resources(
        items=items,
        priority_map=priority_map,
        signals_map=signals_map,
        req_crews=int(req.crews),
        req_trucks=int(req.trucksPerCrew),
        req_workers=int(req.workersPerCrew),
    )

    crews = max(1, min(int(recommended_crews), len(items)))
    max_total = crews * max(1, int(req.maxStopsPerCrew))

    items = sorted(items, key=lambda x: priority_map.get(x.wardId, x.riskScore), reverse=True)[:max_total]

    clusters = cluster_points(items, crews)
    clusters = merge_tiny_clusters(clusters, min_cluster_size=3)

    crew_plans: List[CrewPlan] = []

    for crew_no, cluster in enumerate(clusters, start=1):
        cluster = cluster[: max(1, int(req.maxStopsPerCrew))]
        ordered = order_priority_aware_nearest_neighbor(cluster, priority_map)

        crew_demand_score = sum(priority_map.get(p.wardId, p.riskScore) for p in ordered)
        crew_stop_count = len(ordered)
        crew_high_missed = sum(signals_map.get(p.wardId, {}).get("highMissedCount", 0.0) for p in ordered)
        crew_missed = sum(signals_map.get(p.wardId, {}).get("missedCount", 0.0) for p in ordered)
        crew_unresolved = sum(signals_map.get(p.wardId, {}).get("unresolvedComplaints", 0.0) for p in ordered)
        crew_complaints = sum(signals_map.get(p.wardId, {}).get("complaintsCount", 0.0) for p in ordered)
        crew_emergency = sum(1 for p in ordered if str(p.riskClass).upper() == "EMERGENCY")

        crew_trucks_allocated = max(
            1,
            2 if crew_emergency >= 3 or crew_high_missed >= 2 or crew_stop_count >= 12 else recommended_trucks
        )

        crew_workers_allocated = max(
            2,
            6 if crew_emergency >= 3 or crew_unresolved >= 7 else
            5 if crew_emergency >= 2 or crew_high_missed >= 2 or crew_complaints >= 6 else
            4 if crew_demand_score >= 16 or crew_stop_count >= 9 else
            3 if crew_demand_score >= 8 else
            recommended_workers
        )

        points_latlng: List[Tuple[float, float]] = [(depot["lat"], depot["lng"])] + [(p.lat, p.lng) for p in ordered]

        route = osrm_route(points_latlng)
        polyline = None
        if route and route.get("geometry") and route["geometry"].get("coordinates"):
            coords = route["geometry"]["coordinates"]
            polyline = [[c[1], c[0]] for c in coords]

        table = osrm_table(points_latlng)
        durations = (table or {}).get("durations")
        distances = (table or {}).get("distances")

        stops: List[RouteStop] = []
        prev = (depot["lat"], depot["lng"])

        for idx, p in enumerate(ordered, start=1):
            leg = RouteLeg(mode="Fallback", distanceM=None, durationS=None)

            if durations and distances:
                try:
                    d_s = durations[idx - 1][idx]
                    d_m = distances[idx - 1][idx]
                    if d_s is not None and d_s > 0 and d_m is not None and d_m > 0:
                        leg = RouteLeg(mode="OSRM", distanceM=float(d_m), durationS=float(d_s))
                    else:
                        raise Exception("bad osrm leg")
                except Exception:
                    dist_m = haversine_m(prev, (p.lat, p.lng))
                    dur_s = max(60.0, dist_m / 5.0)
                    leg = RouteLeg(mode="Fallback", distanceM=float(dist_m), durationS=float(dur_s))
            else:
                dist_m = haversine_m(prev, (p.lat, p.lng))
                dur_s = max(60.0, dist_m / 5.0)
                leg = RouteLeg(mode="Fallback", distanceM=float(dist_m), durationS=float(dur_s))

            stops.append(
                RouteStop(
                    stopNo=idx,
                    wardId=p.wardId,
                    wardName=p.wardName,
                    lat=p.lat,
                    lng=p.lng,
                    riskClass=p.riskClass,
                    riskScore=float(p.riskScore),
                    priorityScore=float(priority_map.get(p.wardId, p.riskScore)),
                    boostReason=reason_map.get(p.wardId, "base-risk"),
                    leg=leg,
                )
            )
            prev = (p.lat, p.lng)

        crew_plans.append(
            CrewPlan(
                crewNo=crew_no,
                depot=depot,
                stops=stops,
                polyline=polyline,
                trucksAllocated=crew_trucks_allocated,
                workersAllocated=crew_workers_allocated,
                demandScore=float(crew_demand_score),
            )
        )

    total_stops = sum(len(c.stops) for c in crew_plans)

    return ActionPlanResponse(
        tsPrediction=req.tsPrediction,
        strategy="practical-priority + balanced-crews + tiny-cluster-merge + urgency/travel-balanced ordering + OSRM legs + fallback haversine",
        totalStops=total_stops,
        crews=len(crew_plans),
        recommendedCrewCount=len(crew_plans),
        recommendedTrucksPerCrew=recommended_trucks,
        recommendedWorkersPerCrew=recommended_workers,
        crewPlans=crew_plans,
    )