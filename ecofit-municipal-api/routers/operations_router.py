from __future__ import annotations

import os
import asyncio
from typing import List, Optional, Dict, Any, Tuple
from math import radians, sin, cos, asin, sqrt, ceil, floor
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from database import database

load_dotenv()

router = APIRouter(prefix="/api/v1/operations", tags=["operations"])

OSRM_BASE = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org")
SERVICE_LOGS_COL = os.getenv("SERVICE_LOGS_COL", "service_logs")
COMPLAINTS_COL = os.getenv("COMPLAINTS_COL", "complaints")
MAX_DOCS = int(os.getenv("OPERATIONS_MAX_DOCS", "20000"))


def haversine_m(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    R = 6371000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    s = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * R * asin(sqrt(s))


def approx_travel_minutes(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return max(1.0, haversine_m(a, b) / 366.0)


def osrm_coords(points_latlng: List[Tuple[float, float]]) -> str:
    return ";".join([f"{lng:.6f},{lat:.6f}" for (lat, lng) in points_latlng])


async def osrm_route(points_latlng: List[Tuple[float, float]]) -> Optional[Dict[str, Any]]:
    if len(points_latlng) < 2:
        return None
    coords = osrm_coords(points_latlng)
    url = f"{OSRM_BASE}/route/v1/driving/{coords}"
    params = {"overview": "full", "geometries": "geojson", "steps": "false"}
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            r = await client.get(url, params=params)
        if not r.is_success:
            return None
        data = r.json()
        routes = data.get("routes") or []
        if not routes:
            return None
        best = routes[0]
        return {
            "geometry": best.get("geometry"),
            "distance_m": best.get("distance"),
            "duration_s": best.get("duration"),
        }
    except Exception:
        return None


async def osrm_table(points_latlng: List[Tuple[float, float]]) -> Optional[Dict[str, Any]]:
    if len(points_latlng) < 2:
        return None
    coords = osrm_coords(points_latlng)
    url = f"{OSRM_BASE}/table/v1/driving/{coords}"
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            r = await client.get(url, params={"annotations": "duration,distance"})
        if not r.is_success:
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
    if rc == "EMERGENCY": return 3.2
    if rc == "HIGH": return 1.7
    if rc == "MEDIUM": return 0.7
    return 0.0


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


def cluster_points(points: List[WardPoint], k: int) -> List[List[WardPoint]]:
    k = max(1, min(k, len(points)))
    try:
        from sklearn.cluster import KMeans
        import numpy as np
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
    clusters: List[List[WardPoint]], min_cluster_size: int = 3
) -> List[List[WardPoint]]:
    if len(clusters) <= 1:
        return clusters
    large = [c[:] for c in clusters if len(c) >= min_cluster_size]
    tiny  = [c[:] for c in clusters if len(c) < min_cluster_size]
    if not tiny or not large:
        return clusters

    def center(cluster):
        return (
            sum(p.lat for p in cluster) / len(cluster),
            sum(p.lng for p in cluster) / len(cluster),
        )

    for small in tiny:
        best_i = min(range(len(large)), key=lambda i: haversine_m(center(small), center(large[i])))
        large[best_i].extend(small)
    large.sort(key=lambda c: len(c), reverse=True)
    return large


def order_priority_aware_nearest_neighbor(
    points: List[WardPoint],
    priority_map: Dict[str, float],
    depot_pos: Tuple[float, float] = (6.9271, 79.8612),
) -> List[WardPoint]:
    """
    Step 1: Nearest neighbor from depot.
    Step 2: 2-opt improvement to eliminate crossings.
    """
    if not points:
        return []
    if len(points) == 1:
        return points

    # Step 1: nearest neighbor
    remaining = list(points)
    current = min(remaining, key=lambda x: haversine_m(depot_pos, (x.lat, x.lng)))
    remaining.remove(current)
    ordered = [current]

    while remaining:
        last = ordered[-1]
        last_pos = (last.lat, last.lng)
        nearest = min(remaining, key=lambda p: haversine_m(last_pos, (p.lat, p.lng)))
        remaining.remove(nearest)
        ordered.append(nearest)

    # Step 2: 2-opt
    def total_distance(route: List[WardPoint]) -> float:
        d = haversine_m(depot_pos, (route[0].lat, route[0].lng))
        for i in range(len(route) - 1):
            d += haversine_m(
                (route[i].lat, route[i].lng),
                (route[i + 1].lat, route[i + 1].lng)
            )
        return d

    improved = True
    best_route = ordered[:]
    best_dist = total_distance(best_route)

    while improved:
        improved = False
        for i in range(len(best_route) - 1):
            for j in range(i + 2, len(best_route)):
                new_route = (
                    best_route[:i + 1]
                    + best_route[i + 1:j + 1][::-1]
                    + best_route[j + 1:]
                )
                new_dist = total_distance(new_route)
                if new_dist < best_dist - 1.0:
                    best_route = new_route
                    best_dist = new_dist
                    improved = True
                    break
            if improved:
                break

    return best_route


async def get_recent_operational_signals(
    ward_ids: List[str], hours_back: int = 12
) -> Dict[str, Dict[str, float]]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    ward_set = {w.strip() for w in ward_ids if w and w.strip()}

    signals: Dict[str, Dict[str, float]] = {
        w: {"missedCount": 0.0, "highMissedCount": 0.0,
            "complaintsCount": 0.0, "unresolvedComplaints": 0.0}
        for w in ward_set
    }

    async for d in database[SERVICE_LOGS_COL].find(
        {"createdAt": {"$gte": since}},
        projection={"_id": 0, "wardId": 1, "ward": 1,
                    "outcome": 1, "result": 1, "status": 1, "volumeLevel": 1},
    ).limit(MAX_DOCS):
        wid = extract_ward_id(d)
        if wid not in signals:
            continue
        outcome = str(d.get("outcome") or d.get("result") or d.get("status") or "").upper().strip()
        volume  = str(d.get("volumeLevel") or "").upper().strip()
        if "MISS" in outcome:
            signals[wid]["missedCount"] += 1.0
            if volume == "HIGH":
                signals[wid]["highMissedCount"] += 1.0

    async for d in database[COMPLAINTS_COL].find(
        {"createdAt": {"$gte": since}},
        projection={"_id": 0, "wardId": 1, "ward": 1, "status": 1},
    ).limit(MAX_DOCS):
        wid = extract_ward_id(d)
        if wid not in signals:
            continue
        status = str(d.get("status") or "").upper().strip()
        signals[wid]["complaintsCount"] += 1.0
        if status not in ["RESOLVED", "CLOSED", "REJECTED"]:
            signals[wid]["unresolvedComplaints"] += 1.0

    return signals


def make_priority_score(item: WardPoint, s: Dict[str, float]) -> Tuple[float, str]:
    missed      = s.get("missedCount", 0.0)
    high_missed = s.get("highMissedCount", 0.0)
    complaints  = s.get("complaintsCount", 0.0)
    unresolved  = s.get("unresolvedComplaints", 0.0)
    class_boost = risk_class_weight(item.riskClass)
    boost    = class_boost + missed * 0.35 + high_missed * 0.80 + complaints * 0.12 + unresolved * 0.22
    priority = float(item.riskScore) + boost
    reasons  = []
    if class_boost > 0:  reasons.append(f"class:{item.riskClass}")
    if missed > 0:       reasons.append(f"missed:{int(missed)}")
    if high_missed > 0:  reasons.append(f"highMissed:{int(high_missed)}")
    if unresolved > 0:   reasons.append(f"unresolved:{int(unresolved)}")
    if complaints > 0:   reasons.append(f"complaints:{int(complaints)}")
    return priority, ", ".join(reasons) if reasons else "base-risk"


def recommend_resources(items, priority_map, signals_map, req_crews, req_trucks, req_workers):
    n                  = len(items)
    emergency_count    = sum(1 for x in items if str(x.riskClass).upper() == "EMERGENCY")
    total_high_missed  = sum(signals_map.get(x.wardId, {}).get("highMissedCount", 0.0) for x in items)
    total_missed       = sum(signals_map.get(x.wardId, {}).get("missedCount", 0.0) for x in items)
    total_unresolved   = sum(signals_map.get(x.wardId, {}).get("unresolvedComplaints", 0.0) for x in items)
    total_complaints   = sum(signals_map.get(x.wardId, {}).get("complaintsCount", 0.0) for x in items)
    total_priority     = sum(priority_map.get(x.wardId, x.riskScore) for x in items)

    crews_by_load       = ceil(n / 7)
    max_practical_crews = max(1, floor(n / 4))
    min_practical_crews = max(1, ceil(n / 10))
    demand_pressure     = sum([
        emergency_count >= 8, total_high_missed >= 6,
        total_unresolved >= 10, total_priority >= 120,
    ])
    recommended_crews = max(
        min(max(crews_by_load + demand_pressure, min_practical_crews), max_practical_crews),
        min(req_crews, max_practical_crews),
    )
    recommended_trucks  = max(req_trucks, 2 if emergency_count >= 3 or total_high_missed >= 3 or total_missed >= 6 else 1)
    recommended_workers = max(req_workers,
        5 if emergency_count >= 4 or total_unresolved >= 8 else
        4 if emergency_count >= 2 or total_high_missed >= 2 or total_complaints >= 6 else
        3 if total_complaints >= 3 or total_missed >= 3 else 2)
    return recommended_crews, recommended_trucks, recommended_workers


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
            tsPrediction=req.tsPrediction, strategy="empty", totalStops=0,
            crews=req.crews, recommendedCrewCount=req.crews,
            recommendedTrucksPerCrew=req.trucksPerCrew,
            recommendedWorkersPerCrew=req.workersPerCrew, crewPlans=[],
        )

    ward_ids    = [x.wardId for x in items]
    signals_map = await get_recent_operational_signals(ward_ids, hours_back=12)

    priority_map: Dict[str, float] = {}
    reason_map:   Dict[str, str]   = {}
    for x in items:
        priority, reason = make_priority_score(x, signals_map.get(x.wardId, {}))
        priority_map[x.wardId] = priority
        reason_map[x.wardId]   = reason

    recommended_crews, recommended_trucks, recommended_workers = recommend_resources(
        items, priority_map, signals_map,
        int(req.crews), int(req.trucksPerCrew), int(req.workersPerCrew),
    )

    crews     = max(1, min(int(recommended_crews), len(items)))
    max_total = crews * max(1, int(req.maxStopsPerCrew))
    items     = sorted(items, key=lambda x: priority_map.get(x.wardId, x.riskScore), reverse=True)[:max_total]

    clusters = cluster_points(items, crews)
    clusters = merge_tiny_clusters(clusters, min_cluster_size=3)

    depot_pos = (depot["lat"], depot["lng"])
    crew_plans: List[CrewPlan] = []

    for crew_no, cluster in enumerate(clusters, start=1):
        cluster = cluster[: max(1, int(req.maxStopsPerCrew))]
        ordered = order_priority_aware_nearest_neighbor(
            cluster, priority_map, depot_pos=depot_pos
        )

        crew_demand_score = sum(priority_map.get(p.wardId, p.riskScore) for p in ordered)
        crew_stop_count   = len(ordered)
        crew_emergency    = sum(1 for p in ordered if str(p.riskClass).upper() == "EMERGENCY")
        crew_high_missed  = sum(signals_map.get(p.wardId, {}).get("highMissedCount", 0.0) for p in ordered)
        crew_unresolved   = sum(signals_map.get(p.wardId, {}).get("unresolvedComplaints", 0.0) for p in ordered)
        crew_complaints   = sum(signals_map.get(p.wardId, {}).get("complaintsCount", 0.0) for p in ordered)

        points_latlng = [(depot["lat"], depot["lng"])] + [(p.lat, p.lng) for p in ordered]

        route_result, table = await asyncio.gather(
            osrm_route(points_latlng),
            osrm_table(points_latlng),
        )

        polyline = None
        if route_result and route_result.get("geometry") and route_result["geometry"].get("coordinates"):
            polyline = [[c[1], c[0]] for c in route_result["geometry"]["coordinates"]]

        durations = (table or {}).get("durations")
        distances = (table or {}).get("distances")

        stops: List[RouteStop] = []
        prev = (depot["lat"], depot["lng"])

        for idx, p in enumerate(ordered, start=1):
            if durations and distances:
                try:
                    d_s = durations[idx - 1][idx]
                    d_m = distances[idx - 1][idx]
                    if d_s and d_s > 0 and d_m and d_m > 0:
                        leg = RouteLeg(mode="OSRM", distanceM=float(d_m), durationS=float(d_s))
                    else:
                        raise ValueError("bad osrm leg")
                except Exception:
                    dist_m = haversine_m(prev, (p.lat, p.lng))
                    leg = RouteLeg(mode="Fallback", distanceM=float(dist_m), durationS=max(60.0, dist_m / 5.0))
            else:
                dist_m = haversine_m(prev, (p.lat, p.lng))
                leg = RouteLeg(mode="Fallback", distanceM=float(dist_m), durationS=max(60.0, dist_m / 5.0))

            stops.append(RouteStop(
                stopNo=idx, wardId=p.wardId, wardName=p.wardName,
                lat=p.lat, lng=p.lng, riskClass=p.riskClass,
                riskScore=float(p.riskScore),
                priorityScore=float(priority_map.get(p.wardId, p.riskScore)),
                boostReason=reason_map.get(p.wardId, "base-risk"),
                leg=leg,
            ))
            prev = (p.lat, p.lng)

        # --- Dynamic resource allocation per crew ---
        # Total route distance for this crew
        crew_total_km = sum(
            (s.leg.distanceM or 0) / 1000
            for s in stops
            if s.leg and s.leg.distanceM
        )

        # Waste load score: weighted combination of stops, emergency, missed
        waste_load_score = (
            crew_stop_count * 1.0
            + crew_emergency * 2.0
            + crew_high_missed * 1.5
            + crew_unresolved * 0.5
        )

        # Trucks: 1 per 6 stops base + bonus for emergencies + large area
        base_trucks = max(1, round(crew_stop_count / 6))
        emergency_truck_bonus = crew_emergency // 3
        distance_truck_bonus = 1 if crew_total_km > 10 else 0
        crew_trucks_allocated = min(4, base_trucks + emergency_truck_bonus + distance_truck_bonus)

        # Workers: 2 per truck base + demand bonus + complaint bonus
        base_workers = crew_trucks_allocated * 2
        if waste_load_score >= 20:   demand_worker_bonus = 3
        elif waste_load_score >= 14: demand_worker_bonus = 2
        elif waste_load_score >= 8:  demand_worker_bonus = 1
        else:                        demand_worker_bonus = 0
        complaint_bonus = 1 if crew_unresolved >= 5 else 0
        crew_workers_allocated = min(10, max(2, base_workers + demand_worker_bonus + complaint_bonus))

        crew_plans.append(CrewPlan(
            crewNo=crew_no, depot=depot, stops=stops, polyline=polyline,
            trucksAllocated=crew_trucks_allocated,
            workersAllocated=crew_workers_allocated,
            demandScore=float(crew_demand_score),
        ))

    return ActionPlanResponse(
        tsPrediction=req.tsPrediction,
        strategy="nearest-neighbor + 2-opt + dynamic resource allocation + OSRM async parallel + fallback haversine",
        totalStops=sum(len(c.stops) for c in crew_plans),
        crews=len(crew_plans),
        recommendedCrewCount=len(crew_plans),
        recommendedTrucksPerCrew=recommended_trucks,
        recommendedWorkersPerCrew=recommended_workers,
        crewPlans=crew_plans,
    )