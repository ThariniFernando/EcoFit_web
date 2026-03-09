// src/features/operations/pages/ActionPlanPage.tsx
import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import {
  MapContainer,
  TileLayer,
  Polyline,
  Marker,
  Tooltip,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";

import L, { type LatLngExpression } from "leaflet";

import QuickNav from "../../../app/layout/QuickNav";

import {
  generateActionPlan,
  type ActionPlanResponse,
  type WardPoint,
  type CrewPlan,
  type RouteStop,
} from "../api/operationsApi";

const DEPOT_FALLBACK = { name: "Depot (Town Hall)", lat: 6.9271, lng: 79.8612 };

type NavState = {
  tsPrediction: string | null;
  items: WardPoint[];
  recommendedCrewCount?: number;
  recommendedTrucksPerCrew?: number;
  recommendedWorkersPerCrew?: number;
};

function makeNumberIcon(text: string, bg: string) {
  return L.divIcon({
    className: "",
    html: `
      <div style="
        width:36px;height:36px;border-radius:18px;
        background:${bg};
        border:3px solid white;
        box-shadow: 0 2px 8px rgba(0,0,0,.25);
        display:flex;align-items:center;justify-content:center;
        font-weight:900;color:white;font-size:14px;
      ">${text}</div>
    `,
    iconSize: [36, 36],
    iconAnchor: [18, 18],
  });
}

function fmtHHMM(totalMinutes: number): string {
  const h = Math.floor(totalMinutes / 60);
  const m = totalMinutes % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function kmOrDashFromMeters(m?: number | null): string {
  if (m == null || m <= 0) return "—";
  return (m / 1000).toFixed(2);
}

function minOrDashFromSeconds(s?: number | null): string {
  if (s == null || s <= 0) return "—";
  const min = Math.max(1, Math.round(s / 60));
  return String(min);
}

function jitterLatLng(lat: number, lng: number, key: string) {
  let h = 2166136261;
  for (let i = 0; i < key.length; i++) {
    h ^= key.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }

  const r1 = ((h >>> 0) % 1000) / 1000;
  const r2 = (((h >>> 10) >>> 0) % 1000) / 1000;

  const maxMeters = 20;
  const angle = r1 * Math.PI * 2;
  const radius = r2 * maxMeters;

  const dNorth = Math.cos(angle) * radius;
  const dEast = Math.sin(angle) * radius;

  const dLat = dNorth / 111320;
  const dLng = dEast / (111320 * Math.cos((lat * Math.PI) / 180));

  return { lat: lat + dLat, lng: lng + dLng };
}

function safeArray<T>(x: unknown): T[] {
  return Array.isArray(x) ? (x as T[]) : [];
}

export default function ActionPlanPage() {
  const nav = useNavigate();
  const loc = useLocation();
  const state = (loc.state || {}) as NavState;

  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [plan, setPlan] = useState<ActionPlanResponse | null>(null);
  const [activeCrewNo, setActiveCrewNo] = useState<number>(1);

  const items = useMemo(() => safeArray<WardPoint>(state.items), [state.items]);
  const tsPrediction = state.tsPrediction || null;

  const [crewCount, setCrewCount] = useState<number>(state.recommendedCrewCount ?? 3);
  const [maxStopsPerCrew, setMaxStopsPerCrew] = useState<number>(25);
  const [trucksPerCrew, setTrucksPerCrew] = useState<number>(state.recommendedTrucksPerCrew ?? 1);
  const [workersPerCrew, setWorkersPerCrew] = useState<number>(state.recommendedWorkersPerCrew ?? 2);

  const [startHour, setStartHour] = useState<number>(8);
  const [startMinute, setStartMinute] = useState<number>(0);
  const [serviceMinutesPerStop, setServiceMinutesPerStop] = useState<number>(10);

  const crewPlans = useMemo(() => safeArray<CrewPlan>(plan?.crewPlans), [plan?.crewPlans]);

  const depot = useMemo(() => {
    const active = crewPlans.find((c) => c.crewNo === activeCrewNo);
    const first = crewPlans[0];
    return active?.depot || first?.depot || DEPOT_FALLBACK;
  }, [crewPlans, activeCrewNo]);

  const mapCenter = useMemo<[number, number]>(() => [depot.lat, depot.lng], [depot.lat, depot.lng]);

  async function buildPlan() {
    setLoading(true);
    setErr(null);

    try {
      if (!tsPrediction) {
        throw new Error("Missing tsPrediction. Go back to Risk Map and generate the plan again.");
      }

      if (!items.length) {
        throw new Error("No wards/items received from Risk Map.");
      }

      const payload = {
        tsPrediction,
        items,
        crews: crewCount,
        maxStopsPerCrew,
        trucksPerCrew,
        workersPerCrew,
        serviceMinutesPerStop,
      };

      const res = await generateActionPlan(payload);
      setPlan(res);

      if (typeof res.recommendedCrewCount === "number" && res.recommendedCrewCount > 0) {
        setCrewCount(res.recommendedCrewCount);
      }
      if (typeof res.recommendedTrucksPerCrew === "number" && res.recommendedTrucksPerCrew > 0) {
        setTrucksPerCrew(res.recommendedTrucksPerCrew);
      }
      if (typeof res.recommendedWorkersPerCrew === "number" && res.recommendedWorkersPerCrew > 0) {
        setWorkersPerCrew(res.recommendedWorkersPerCrew);
      }

      const plans = safeArray<CrewPlan>(res.crewPlans);
      const maxCrewNo = plans.length ? Math.max(...plans.map((c) => c.crewNo)) : 1;
      setActiveCrewNo((prev) => Math.min(Math.max(1, prev), maxCrewNo));
    } catch (e: any) {
      setErr(e?.message || "Failed to generate plan");
      setPlan(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!items.length || !tsPrediction) return;
    buildPlan();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const activeCrew: CrewPlan | null = useMemo(() => {
    if (!crewPlans.length) return null;
    return crewPlans.find((c) => c.crewNo === activeCrewNo) || crewPlans[0] || null;
  }, [crewPlans, activeCrewNo]);

  const polylinePositions: LatLngExpression[] = useMemo(() => {
    const poly = activeCrew?.polyline;
    if (!Array.isArray(poly) || !poly.length) return [];
    return poly.map((p) => [p[0], p[1]] as LatLngExpression);
  }, [activeCrew]);

  const scheduledRows = useMemo(() => {
    if (!activeCrew) return [];

    const stops = safeArray<RouteStop>(activeCrew.stops);
    const start = startHour * 60 + startMinute;
    let t = start;

    const rows: Array<{
      stopLabel: string;
      eta: string;
      legKm: string;
      legMin: string;
      ward: string;
      risk: string;
      score: string;
      priority: string;
      reason: string;
      mode: string;
    }> = [];

    rows.push({
      stopLabel: "D",
      eta: fmtHHMM(t),
      legKm: "—",
      legMin: "—",
      ward: activeCrew.depot?.name || depot.name,
      risk: "START",
      score: "—",
      priority: "—",
      reason: "—",
      mode: "—",
    });

    for (let i = 0; i < stops.length; i++) {
      const s = stops[i];
      const legS = s.leg?.durationS ?? null;
      const legM = s.leg?.distanceM ?? null;
      const mode = s.leg?.mode || "Fallback";

      if (legS != null && legS > 0) {
        t += Math.max(1, Math.round(legS / 60));
      } else {
        t += 3;
      }

      rows.push({
        stopLabel: `#${s.stopNo}`,
        eta: fmtHHMM(t),
        legKm: kmOrDashFromMeters(legM),
        legMin: minOrDashFromSeconds(legS),
        ward: s.wardName || s.wardId,
        risk: s.riskClass,
        score: Number.isFinite(s.riskScore) ? s.riskScore.toFixed(3) : "—",
        priority: typeof s.priorityScore === "number" ? s.priorityScore.toFixed(3) : "—",
        reason: s.boostReason || "base-risk",
        mode,
      });

      t += Math.max(1, serviceMinutesPerStop);
    }

    return rows;
  }, [activeCrew, depot.name, startHour, startMinute, serviceMinutesPerStop]);

  const markers = useMemo(() => {
    if (!activeCrew) return [];

    const stops = safeArray<RouteStop>(activeCrew.stops);

    const m: Array<{
      key: string;
      pos: LatLngExpression;
      icon: L.DivIcon;
      label: string;
    }> = [];

    const depotName = activeCrew.depot?.name || depot.name;
    const depotLat = activeCrew.depot?.lat ?? depot.lat;
    const depotLng = activeCrew.depot?.lng ?? depot.lng;

    m.push({
      key: `depot-${activeCrew.crewNo}`,
      pos: [depotLat, depotLng],
      icon: makeNumberIcon("D", "#111"),
      label: depotName,
    });

    for (const s of stops) {
      const bg = "#e74c3c";
      const j = jitterLatLng(s.lat, s.lng, `${activeCrew.crewNo}-${s.stopNo}-${s.wardId}`);

      m.push({
        key: `stop-${activeCrew.crewNo}-${s.stopNo}-${s.wardId}`,
        pos: [j.lat, j.lng],
        icon: makeNumberIcon(String(s.stopNo), bg),
        label: `${s.stopNo}. ${s.wardName || s.wardId} (${s.riskClass} • ${s.riskScore.toFixed(3)}${
          typeof s.priorityScore === "number" ? ` • priority ${s.priorityScore.toFixed(3)}` : ""
        })`,
      });
    }

    return m;
  }, [activeCrew, depot.lat, depot.lng, depot.name]);

  const wardsPassed = items.length;

  const totalDemand = useMemo(() => {
    return crewPlans.reduce((sum, c) => sum + (c.demandScore || 0), 0);
  }, [crewPlans]);

  return (
    <div style={{ padding: 16 }}>
      <QuickNav />

      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
        }}
      >
        <div>
          <h2 style={{ margin: 0 }}>Action Plan</h2>
          <div style={{ marginTop: 6, color: "#555" }}>
            Prediction Time: <b>{tsPrediction || plan?.tsPrediction || "—"}</b> | Wards passed: <b>{wardsPassed}</b>
            {loading ? " | Building road routes (OSRM)…" : ""}
            {err ? <span style={{ color: "#c0392b" }}> | {err}</span> : null}
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <button
            onClick={() => nav("/risk-map")}
            style={{
              padding: "10px 16px",
              borderRadius: 12,
              border: "none",
              background: "rgb(45 106 79)",
              color: "white",
              fontWeight: 700,
              cursor: "pointer",
              height: 40,
              boxShadow: "0 2px 6px rgba(0,0,0,.15)",
              alignSelf: "flex-start",
              transition: "all 0.2s ease",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.transform = "translateY(-2px)")}
            onMouseLeave={(e) => (e.currentTarget.style.transform = "translateY(0)")}
          >
            ← Back to Risk Map
          </button>

          

          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ color: "#666" }}>Max stops/crew</span>
            <input
              value={maxStopsPerCrew}
              type="number"
              min={1}
              max={100}
              onChange={(e) => setMaxStopsPerCrew(Number(e.target.value))}
              style={{ width: 90, padding: "6px 8px", borderRadius: 10, border: "1px solid #ccc" }}
            />
          </div>

          <button
            onClick={buildPlan}
            style={{
              padding: "8px 12px",
              borderRadius: 10,
              border: "1px solid #ccc",
              background: "white",
              cursor: "pointer",
              fontWeight: 700,
            }}
            disabled={loading || !items.length || !tsPrediction}
          >
            Re-generate Plan
          </button>
        </div>
      </div>

      <div style={{ marginTop: 12, display: "grid", gridTemplateColumns: "1fr 520px", gap: 12 }}>
        <div style={{ borderRadius: 14, overflow: "hidden", border: "1px solid #e6e6e6" }}>
          <MapContainer center={mapCenter} zoom={13} style={{ height: 620, width: "100%" }}>
            <TileLayer
              attribution="&copy; OpenStreetMap contributors"
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />

            {polylinePositions.length ? (
              <Polyline positions={polylinePositions} pathOptions={{ weight: 5, opacity: 0.85 }} />
            ) : null}

            {markers.map((m) => (
              <Marker key={m.key} position={m.pos} icon={m.icon}>
                <Tooltip direction="top" offset={[0, -10]} opacity={1}>
                  <div style={{ fontWeight: 800 }}>{m.label}</div>
                </Tooltip>
              </Marker>
            ))}
          </MapContainer>
        </div>

        <div style={{ borderRadius: 14, border: "1px solid #e6e6e6", padding: 12, height: 620, overflow: "auto" }}>
          <div style={{ fontSize: 16, fontWeight: 900 }}>Plan Summary</div>

          {/* <div style={{ marginTop: 8, fontSize: 13, color: "#444", lineHeight: 1.6 }}>
            <div>
              <b>Strategy:</b> {plan?.strategy || "—"}
            </div>
            <div>
              <b>Total stops:</b> {plan?.totalStops ?? items.length}
            </div>
            <div>
              <b>Recommended crews:</b> {plan?.recommendedCrewCount ?? crewCount}
            </div>
            <div>
              <b>Recommended trucks/crew:</b> {plan?.recommendedTrucksPerCrew ?? trucksPerCrew}
            </div>
            <div>
              <b>Recommended workers/crew:</b> {plan?.recommendedWorkersPerCrew ?? workersPerCrew}
            </div>
            <div>
              <b>Total demand score:</b> {totalDemand.toFixed(3)}
            </div>
            <div>
              <b>Depot:</b> {depot.name} ({depot.lat.toFixed(4)}, {depot.lng.toFixed(4)})
            </div>
          </div> */}

          <div style={{ marginTop: 10, display: "grid", gap: 8, fontSize: 13 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "#666" }}>Strategy</span>
              <b>{plan?.strategy || "—"}</b>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "#666" }}>Total stops</span>
              <b>{plan?.totalStops ?? items.length}</b>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "#666" }}>Recommended crews</span>
              <b>{plan?.recommendedCrewCount ?? crewCount}</b>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "#666" }}>Trucks per crew</span>
              <b>{plan?.recommendedTrucksPerCrew ?? trucksPerCrew}</b>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "#666" }}>Workers per crew</span>
              <b>{plan?.recommendedWorkersPerCrew ?? workersPerCrew}</b>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "#666" }}>Total demand score</span>
              <b>{totalDemand.toFixed(3)}</b>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "#666" }}>Depot</span>
              <b>
                {depot.name} ({depot.lat.toFixed(4)}, {depot.lng.toFixed(4)})
              </b>
            </div>
          </div>

          <div style={{ marginTop: 12, display: "flex", gap: 10, flexWrap: "wrap" }}>
            {crewPlans.map((c) => (
              <button
                key={c.crewNo}
                onClick={() => setActiveCrewNo(c.crewNo)}
                style={{
                  padding: "8px 12px",
                  borderRadius: 12,
                  border: activeCrewNo === c.crewNo ? "2px solid #111" : "1px solid #ddd",
                  background: "white",
                  cursor: "pointer",
                  fontWeight: 800,
                }}
              >
                Crew {c.crewNo}
              </button>
            ))}
          </div>

          {activeCrew ? (
            <div style={{ marginTop: 14, borderTop: "1px solid #eee", paddingTop: 12 }}>
              <div style={{ fontSize: 14, fontWeight: 900 }}>Selected Crew Resource Allocation</div>

              <div style={{ marginTop: 10, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <div style={{ border: "1px solid #eee", borderRadius: 12, padding: 10 }}>
                  <div style={{ fontSize: 12, color: "#666" }}>Crew</div>
                  <div style={{ fontSize: 18, fontWeight: 900 }}>Crew {activeCrew.crewNo}</div>
                </div>

                <div style={{ border: "1px solid #eee", borderRadius: 12, padding: 10 }}>
                  <div style={{ fontSize: 12, color: "#666" }}>Stops</div>
                  <div style={{ fontSize: 18, fontWeight: 900 }}>{safeArray<RouteStop>(activeCrew.stops).length}</div>
                </div>

                <div style={{ border: "1px solid #eee", borderRadius: 12, padding: 10 }}>
                  <div style={{ fontSize: 12, color: "#666" }}>Trucks allocated</div>
                  <div style={{ fontSize: 18, fontWeight: 900 }}>{activeCrew.trucksAllocated ?? 1}</div>
                </div>

                <div style={{ border: "1px solid #eee", borderRadius: 12, padding: 10 }}>
                  <div style={{ fontSize: 12, color: "#666" }}>Workers allocated</div>
                  <div style={{ fontSize: 18, fontWeight: 900 }}>{activeCrew.workersAllocated ?? 2}</div>
                </div>

                <div style={{ border: "1px solid #eee", borderRadius: 12, padding: 10, gridColumn: "1 / span 2" }}>
                  <div style={{ fontSize: 12, color: "#666" }}>Demand score</div>
                  <div style={{ fontSize: 18, fontWeight: 900 }}>{(activeCrew.demandScore ?? 0).toFixed(3)}</div>
                </div>
              </div>
            </div>
          ) : null}
          {/* 
          <div style={{ marginTop: 14, borderTop: "1px solid #eee", paddingTop: 12 }}>
            <div style={{ fontSize: 14, fontWeight: 900 }}>Route Plan Settings</div>
            <div style={{ marginTop: 8, display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
              <span style={{ color: "#666" }}>Start time:</span>
              <input
                value={startHour}
                type="number"
                min={0}
                max={23}
                onChange={(e) => setStartHour(Number(e.target.value))}
                style={{ width: 70, padding: "6px 8px", borderRadius: 10, border: "1px solid #ccc" }}
              />
              <span>:</span>
              <input
                value={startMinute}
                type="number"
                min={0}
                max={59}
                onChange={(e) => setStartMinute(Number(e.target.value))}
                style={{ width: 70, padding: "6px 8px", borderRadius: 10, border: "1px solid #ccc" }}
              />

              <span style={{ color: "#666", marginLeft: 10 }}>Service minutes/stop:</span>
              <input
                value={serviceMinutesPerStop}
                type="number"
                min={1}
                max={120}
                onChange={(e) => setServiceMinutesPerStop(Number(e.target.value))}
                style={{ width: 90, padding: "6px 8px", borderRadius: 10, border: "1px solid #ccc" }}
              />
            </div>

            <div style={{ marginTop: 6, fontSize: 12, color: "#666" }}>
              Schedule = OSRM travel time per leg + service time per stop. Route order now considers priority boosts and operational demand.
            </div>
          </div> */}

          <div style={{ marginTop: 18, borderTop: "1px solid #eee", paddingTop: 14 }}>
            <div style={{ fontSize: 14, fontWeight: 900, marginBottom: 10 }}>
              Route Plan Settings
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: 12,
                alignItems: "center",
              }}
            >
              <div>
                <div style={{ fontSize: 12, color: "#666", marginBottom: 4 }}>
                  Start Time
                </div>

                <div style={{ display: "flex", gap: 6 }}>
                  <input
                    value={startHour}
                    type="number"
                    min={0}
                    max={23}
                    onChange={(e) => setStartHour(Number(e.target.value))}
                    style={{
                      width: 70,
                      padding: "6px 8px",
                      borderRadius: 10,
                      border: "1px solid #ccc",
                    }}
                  />

                  <input
                    value={startMinute}
                    type="number"
                    min={0}
                    max={59}
                    onChange={(e) => setStartMinute(Number(e.target.value))}
                    style={{
                      width: 70,
                      padding: "6px 8px",
                      borderRadius: 10,
                      border: "1px solid #ccc",
                    }}
                  />
                </div>
              </div>

              <div>
                <div style={{ fontSize: 12, color: "#666", marginBottom: 4 }}>
                  Service Minutes per Stop
                </div>

                <input
                  value={serviceMinutesPerStop}
                  type="number"
                  min={1}
                  max={120}
                  onChange={(e) => setServiceMinutesPerStop(Number(e.target.value))}
                  style={{
                    width: 100,
                    padding: "6px 8px",
                    borderRadius: 10,
                    border: "1px solid #ccc",
                  }}
                />
              </div>
            </div>

            <div style={{ marginTop: 10, fontSize: 12, color: "#777" }}>
              Schedule = OSRM travel time per leg + service time per stop.
            </div>
          </div>

          <div style={{ marginTop: 14, borderTop: "1px solid #eee", paddingTop: 12 }}>
            <div style={{ fontSize: 14, fontWeight: 900 }}>
              Detailed Route Plan (Crew {activeCrewNo})
            </div>

            <div style={{ marginTop: 10, overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, background: "white" }}>
                <thead>
                  <tr style={{ textAlign: "left", borderBottom: "2px solid #eee", background: "#fafafa" }}>
                    <th style={{ padding: "10px 8px", fontWeight: 700 }}>Stop</th>
                    <th style={{ padding: "10px 8px", fontWeight: 700 }}>ETA</th>
                    <th style={{ padding: "10px 8px", fontWeight: 700 }}>Leg (km)</th>
                    <th style={{ padding: "10px 8px", fontWeight: 700 }}>Leg (min)</th>
                    <th style={{ padding: "10px 8px", fontWeight: 700 }}>Ward</th>
                    <th style={{ padding: "10px 8px", fontWeight: 700 }}>Risk</th>
                    <th style={{ padding: "10px 8px", fontWeight: 700 }}>Score</th>
                    <th style={{ padding: "10px 8px", fontWeight: 700 }}>Priority</th>
                    <th style={{ padding: "10px 8px", fontWeight: 700 }}>Reason</th>
                    <th style={{ padding: "10px 8px", fontWeight: 700 }}>Mode</th>
                  </tr>
                </thead>
                <tbody>
                  {scheduledRows.map((r) => (
                    <tr key={`${r.stopLabel}-${r.ward}`} style={{ borderBottom: "1px solid #f2f2f2" }}>
                      <td style={{ padding: "8px 6px", fontWeight: 900 }}>{r.stopLabel}</td>
                      <td style={{ padding: "8px 6px" }}>{r.eta}</td>
                      <td style={{ padding: "8px 6px" }}>{r.legKm}</td>
                      <td style={{ padding: "8px 6px" }}>{r.legMin}</td>
                      <td style={{ padding: "8px 6px" }}>{r.ward}</td>
                      <td
                        style={{
                          padding: "8px 6px",
                          fontWeight: 900,
                          color: r.risk === "EMERGENCY" ? "#e74c3c" : "#333",
                        }}
                      >
                        {r.risk}
                      </td>
                      <td style={{ padding: "8px 6px" }}>{r.score}</td>
                      <td style={{ padding: "8px 6px" }}>{r.priority}</td>
                      <td style={{ padding: "8px 6px", color: "#666" }}>{r.reason}</td>
                      <td style={{ padding: "8px 6px", color: "#666" }}>{r.mode}</td>
                    </tr>
                  ))}

                  {!scheduledRows.length ? (
                    <tr>
                      <td colSpan={10} style={{ padding: 12, color: "#777" }}>
                        No route plan yet.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}