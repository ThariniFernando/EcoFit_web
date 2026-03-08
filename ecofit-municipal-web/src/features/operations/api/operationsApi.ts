// src/features/operations/api/operationsApi.ts

const BASE_URL = "http://127.0.0.1:8000";

export type RiskClass = "LOW" | "MEDIUM" | "HIGH" | "EMERGENCY";

export type WardPoint = {
  wardId: string;
  wardName?: string | null;
  lat: number;
  lng: number;
  riskClass: RiskClass;
  riskScore: number;
};

export type RouteLeg = {
  distanceM?: number | null;
  durationS?: number | null;
  mode?: "OSRM" | "Fallback";
};

export type RouteStop = {
  stopNo: number;
  wardId: string;
  wardName?: string | null;
  lat: number;
  lng: number;
  riskClass: RiskClass;
  riskScore: number;
  priorityScore?: number | null;
  boostReason?: string | null;
  leg?: RouteLeg | null;
};

export type CrewPlan = {
  crewNo: number;
  depot: { name: string; lat: number; lng: number };
  stops: RouteStop[];
  polyline?: Array<[number, number]> | null;
  trucksAllocated: number;
  workersAllocated: number;
  demandScore: number;
};

export type ActionPlanResponse = {
  tsPrediction: string;
  strategy: string;
  totalStops: number;
  crews: number;
  recommendedCrewCount: number;
  recommendedTrucksPerCrew: number;
  recommendedWorkersPerCrew: number;
  crewPlans: CrewPlan[];
};

export type GenerateActionPlanRequest = {
  tsPrediction: string;
  items: WardPoint[];
  crews: number;
  maxStopsPerCrew: number;
  trucksPerCrew: number;
  workersPerCrew: number;
  serviceMinutesPerStop?: number;
  depotLat?: number;
  depotLng?: number;
  depotName?: string;
};

type BackendRouteLeg = {
  distanceM?: number | null;
  durationS?: number | null;
  mode?: "OSRM" | "Fallback";
};

type BackendRouteStop = {
  stopNo: number;
  wardId: string;
  wardName?: string | null;
  lat: number;
  lng: number;
  riskClass: RiskClass;
  riskScore: number;
  priorityScore?: number | null;
  boostReason?: string | null;
  leg?: BackendRouteLeg | null;
};

type BackendCrewPlan = {
  crewNo: number;
  depot: { name: string; lat: number; lng: number };
  stops: BackendRouteStop[];
  polyline?: Array<[number, number]> | null;
  trucksAllocated?: number;
  workersAllocated?: number;
  demandScore?: number;
};

type BackendActionPlanResponse = {
  tsPrediction?: string | null;
  strategy?: string;
  totalStops?: number;
  crews?: number;
  recommendedCrewCount?: number;
  recommendedTrucksPerCrew?: number;
  recommendedWorkersPerCrew?: number;
  crewPlans?: BackendCrewPlan[];
};

function safeArray<T>(x: unknown): T[] {
  return Array.isArray(x) ? (x as T[]) : [];
}

function safeNum(x: unknown, fallback = 0): number {
  return typeof x === "number" && Number.isFinite(x) ? x : fallback;
}

export async function generateActionPlan(
  payload: GenerateActionPlanRequest
): Promise<ActionPlanResponse> {
  const res = await fetch(`${BASE_URL}/api/v1/operations/action-plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || `HTTP ${res.status}`);
  }

  const raw = (await res.json()) as BackendActionPlanResponse;

  const crewPlans: CrewPlan[] = safeArray<BackendCrewPlan>(raw.crewPlans).map((c) => ({
    crewNo: safeNum(c.crewNo, 1),
    depot: c.depot || { name: "Depot (Town Hall)", lat: 6.9271, lng: 79.8612 },
    stops: safeArray<BackendRouteStop>(c.stops).map((s) => ({
      stopNo: safeNum(s.stopNo, 0),
      wardId: s.wardId,
      wardName: s.wardName,
      lat: safeNum(s.lat),
      lng: safeNum(s.lng),
      riskClass: s.riskClass,
      riskScore: safeNum(s.riskScore),
      priorityScore: typeof s.priorityScore === "number" ? s.priorityScore : null,
      boostReason: s.boostReason ?? null,
      leg: s.leg
        ? {
            distanceM: typeof s.leg.distanceM === "number" ? s.leg.distanceM : null,
            durationS: typeof s.leg.durationS === "number" ? s.leg.durationS : null,
            mode: s.leg.mode ?? "Fallback",
          }
        : null,
    })),
    polyline: Array.isArray(c.polyline) ? c.polyline : null,
    trucksAllocated: safeNum(c.trucksAllocated, 1),
    workersAllocated: safeNum(c.workersAllocated, 2),
    demandScore: safeNum(c.demandScore, 0),
  }));

  return {
    tsPrediction: String(raw.tsPrediction || payload.tsPrediction || ""),
    strategy: raw.strategy || "priority-aware + OSRM",
    totalStops: safeNum(raw.totalStops, payload.items.length),
    crews: safeNum(raw.crews, crewPlans.length),
    recommendedCrewCount: safeNum(raw.recommendedCrewCount, crewPlans.length),
    recommendedTrucksPerCrew: safeNum(raw.recommendedTrucksPerCrew, 1),
    recommendedWorkersPerCrew: safeNum(raw.recommendedWorkersPerCrew, 2),
    crewPlans,
  };
}