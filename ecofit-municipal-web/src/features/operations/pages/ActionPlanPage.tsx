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
    html: `<div style="
        width:36px;height:36px;border-radius:18px;
        background:${bg};border:3px solid white;
        box-shadow:0 2px 8px rgba(0,0,0,.25);
        display:flex;align-items:center;justify-content:center;
        font-weight:900;color:white;font-size:14px;">
      ${text}</div>`,
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
  return String(Math.max(1, Math.round(s / 60)));
}

function jitterLatLng(lat: number, lng: number, key: string) {
  let h = 2166136261;
  for (let i = 0; i < key.length; i++) {
    h ^= key.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  const r1 = ((h >>> 0) % 1000) / 1000;
  const r2 = (((h >>> 10) >>> 0) % 1000) / 1000;
  const angle = r1 * Math.PI * 2;
  const radius = r2 * 20;
  const dLat = (Math.cos(angle) * radius) / 111320;
  const dLng = (Math.sin(angle) * radius) / (111320 * Math.cos((lat * Math.PI) / 180));
  return { lat: lat + dLat, lng: lng + dLng };
}

function safeArray<T>(x: unknown): T[] {
  return Array.isArray(x) ? (x as T[]) : [];
}

// Truck/worker load indicator bar
function LoadBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = Math.min(100, Math.round((value / max) * 100));
  return (
    <div style={{ background: "#f0f0f0", borderRadius: 4, height: 6, overflow: "hidden", marginTop: 4 }}>
      <div style={{ width: `${pct}%`, background: color, height: "100%", borderRadius: 4, transition: "width 0.4s ease" }} />
    </div>
  );
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
    return active?.depot || crewPlans[0]?.depot || DEPOT_FALLBACK;
  }, [crewPlans, activeCrewNo]);

  const mapCenter = useMemo<[number, number]>(() => [depot.lat, depot.lng], [depot.lat, depot.lng]);

  // Max values across all crews for load bars
  const maxTrucks = useMemo(() => Math.max(1, ...crewPlans.map(c => c.trucksAllocated ?? 1)), [crewPlans]);
  const maxWorkers = useMemo(() => Math.max(1, ...crewPlans.map(c => c.workersAllocated ?? 2)), [crewPlans]);
  const maxDemand = useMemo(() => Math.max(1, ...crewPlans.map(c => c.demandScore ?? 0)), [crewPlans]);

  async function buildPlan() {
    setLoading(true);
    setErr(null);
    try {
      if (!tsPrediction) throw new Error("Missing tsPrediction. Go back to Risk Map.");
      if (!items.length) throw new Error("No wards received from Risk Map.");

      const res = await generateActionPlan({
        tsPrediction, items, crews: crewCount, maxStopsPerCrew,
        trucksPerCrew, workersPerCrew, serviceMinutesPerStop,
      });
      setPlan(res);

      if (res.recommendedCrewCount > 0) setCrewCount(res.recommendedCrewCount);
      if (res.recommendedTrucksPerCrew > 0) setTrucksPerCrew(res.recommendedTrucksPerCrew);
      if (res.recommendedWorkersPerCrew > 0) setWorkersPerCrew(res.recommendedWorkersPerCrew);

      const plans = safeArray<CrewPlan>(res.crewPlans);
      const maxNo = plans.length ? Math.max(...plans.map(c => c.crewNo)) : 1;
      setActiveCrewNo(prev => Math.min(Math.max(1, prev), maxNo));
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

  const activeCrew = useMemo(() =>
    crewPlans.find(c => c.crewNo === activeCrewNo) || crewPlans[0] || null,
    [crewPlans, activeCrewNo]
  );

  const polylinePositions: LatLngExpression[] = useMemo(() => {
    const poly = activeCrew?.polyline;
    if (!Array.isArray(poly) || !poly.length) return [];
    return poly.map(p => [p[0], p[1]] as LatLngExpression);
  }, [activeCrew]);

  const scheduledRows = useMemo(() => {
    if (!activeCrew) return [];
    const stops = safeArray<RouteStop>(activeCrew.stops);
    let t = startHour * 60 + startMinute;
    const rows: any[] = [{
      stopLabel: "D", eta: fmtHHMM(t), legKm: "—", legMin: "—",
      ward: activeCrew.depot?.name || depot.name, risk: "START",
      score: "—", priority: "—", reason: "—", mode: "—",
    }];
    for (const s of stops) {
      const legS = s.leg?.durationS ?? null;
      const legM = s.leg?.distanceM ?? null;
      if (legS != null && legS > 0) t += Math.max(1, Math.round(legS / 60));
      else t += 3;
      rows.push({
        stopLabel: `#${s.stopNo}`, eta: fmtHHMM(t),
        legKm: kmOrDashFromMeters(legM), legMin: minOrDashFromSeconds(legS),
        ward: s.wardName || s.wardId, risk: s.riskClass,
        score: Number.isFinite(s.riskScore) ? s.riskScore.toFixed(3) : "—",
        priority: typeof s.priorityScore === "number" ? s.priorityScore.toFixed(3) : "—",
        reason: s.boostReason || "base-risk", mode: s.leg?.mode || "Fallback",
      });
      t += Math.max(1, serviceMinutesPerStop);
    }
    return rows;
  }, [activeCrew, depot.name, startHour, startMinute, serviceMinutesPerStop]);

  const markers = useMemo(() => {
    if (!activeCrew) return [];
    const stops = safeArray<RouteStop>(activeCrew.stops);
    const m: any[] = [{
      key: `depot-${activeCrew.crewNo}`,
      pos: [activeCrew.depot?.lat ?? depot.lat, activeCrew.depot?.lng ?? depot.lng],
      icon: makeNumberIcon("D", "#111"),
      label: activeCrew.depot?.name || depot.name,
    }];
    for (const s of stops) {
      const j = jitterLatLng(s.lat, s.lng, `${activeCrew.crewNo}-${s.stopNo}-${s.wardId}`);
      m.push({
        key: `stop-${activeCrew.crewNo}-${s.stopNo}-${s.wardId}`,
        pos: [j.lat, j.lng],
        icon: makeNumberIcon(String(s.stopNo), "#e74c3c"),
        label: `${s.stopNo}. ${s.wardName || s.wardId} (${s.riskClass} • ${s.riskScore.toFixed(3)})`,
      });
    }
    return m;
  }, [activeCrew, depot]);

  const totalDemand = useMemo(() =>
    crewPlans.reduce((sum, c) => sum + (c.demandScore || 0), 0),
    [crewPlans]
  );

  function exportPDF() {
    if (!plan) return;
    const allCrewRows = crewPlans.map((crew) => {
      const stops = safeArray<RouteStop>(crew.stops);
      let t = startHour * 60 + startMinute;
      let rows = `<tr style="background:#f5f5f5;">
        <td style="padding:6px 8px;font-weight:900;">D</td>
        <td>${fmtHHMM(t)}</td><td>—</td><td>—</td>
        <td>${crew.depot?.name || "Depot"}</td>
        <td>START</td><td>—</td><td>—</td></tr>`;
      for (const s of stops) {
        const legS = s.leg?.durationS ?? null;
        const legM = s.leg?.distanceM ?? null;
        if (legS != null && legS > 0) t += Math.max(1, Math.round(legS / 60));
        else t += 3;
        t += Math.max(1, serviceMinutesPerStop);
        const rc = s.riskClass === "EMERGENCY" ? "#e74c3c" : s.riskClass === "HIGH" ? "#e67e22" : s.riskClass === "MEDIUM" ? "#f1c40f" : "#2ecc71";
        rows += `<tr style="border-bottom:1px solid #eee;">
          <td style="padding:6px 8px;font-weight:900;">#${s.stopNo}</td>
          <td>${fmtHHMM(t)}</td>
          <td>${kmOrDashFromMeters(legM)}</td>
          <td>${minOrDashFromSeconds(legS)}</td>
          <td>${s.wardName || s.wardId}</td>
          <td style="color:${rc};font-weight:700;">${s.riskClass}</td>
          <td>${s.riskScore.toFixed(3)}</td>
          <td>${typeof s.priorityScore === "number" ? s.priorityScore.toFixed(3) : "—"}</td></tr>`;
      }
      return `<div style="margin-bottom:24px;page-break-inside:avoid;">
        <h3 style="margin:0 0 6px;font-size:15px;border-bottom:2px solid #333;padding-bottom:4px;">
          Crew ${crew.crewNo} — ${stops.length} stops | Trucks: ${crew.trucksAllocated} | Workers: ${crew.workersAllocated} | Demand: ${(crew.demandScore||0).toFixed(3)}
        </h3>
        <table style="width:100%;border-collapse:collapse;font-size:12px;">
          <thead><tr style="background:#333;color:white;">
            <th style="padding:6px 8px;text-align:left;">Stop</th>
            <th style="padding:6px 8px;text-align:left;">ETA</th>
            <th style="padding:6px 8px;text-align:left;">Leg (km)</th>
            <th style="padding:6px 8px;text-align:left;">Leg (min)</th>
            <th style="padding:6px 8px;text-align:left;">Ward</th>
            <th style="padding:6px 8px;text-align:left;">Risk</th>
            <th style="padding:6px 8px;text-align:left;">Score</th>
            <th style="padding:6px 8px;text-align:left;">Priority</th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table></div>`;
    }).join("");

    const html = `<!DOCTYPE html><html><head><title>EcoFit Action Plan</title>
      <style>
        body{font-family:Arial,sans-serif;padding:24px;color:#222;}
        h1{font-size:20px;margin:0 0 4px;}
        .meta{font-size:12px;color:#666;margin-bottom:16px;}
        .summary{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:20px;}
        .stat{border:1px solid #ddd;border-radius:8px;padding:10px 14px;}
        .stat-label{font-size:11px;color:#888;}
        .stat-value{font-size:20px;font-weight:900;}
        @media print{@page{margin:16mm;size:A4 landscape;}body{padding:0;}}
      </style></head><body>
      <h1>EcoFit Municipal — Action Plan</h1>
      <div class="meta">Generated: ${new Date().toLocaleString()} | Prediction: ${tsPrediction || plan.tsPrediction} | ${plan.strategy}</div>
      <div class="summary">
        <div class="stat"><div class="stat-label">Total stops</div><div class="stat-value">${plan.totalStops}</div></div>
        <div class="stat"><div class="stat-label">Crews</div><div class="stat-value">${plan.recommendedCrewCount}</div></div>
        <div class="stat"><div class="stat-label">Total demand</div><div class="stat-value">${totalDemand.toFixed(1)}</div></div>
        <div class="stat"><div class="stat-label">Depot</div><div class="stat-value" style="font-size:13px;">${crewPlans[0]?.depot?.name || "Town Hall"}</div></div>
      </div>
      ${allCrewRows}
      <div style="margin-top:16px;font-size:11px;color:#aaa;border-top:1px solid #eee;padding-top:8px;">
        EcoFit Municipal Operations Platform
      </div></body></html>`;

    const w = window.open("", "_blank");
    if (!w) return;
    w.document.write(html);
    w.document.close();
    w.focus();
    setTimeout(() => w.print(), 500);
  }

  return (
    <div style={{ padding: 16 }}>
      <QuickNav />

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <div>
          <h2 style={{ margin: 0 }}>Action Plan</h2>
          <div style={{ marginTop: 6, color: "#555" }}>
            Prediction Time: <b>{tsPrediction || plan?.tsPrediction || "—"}</b> | Wards: <b>{items.length}</b>
            {loading ? " | Generating…" : ""}
            {err ? <span style={{ color: "#c0392b" }}> | {err}</span> : null}
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <button onClick={() => nav("/risk-map")}
            style={{ padding: "10px 16px", borderRadius: 12, border: "none", background: "rgb(45 106 79)", color: "white", fontWeight: 700, cursor: "pointer", height: 40, transition: "all 0.2s ease" }}
            onMouseEnter={e => (e.currentTarget.style.transform = "translateY(-2px)")}
            onMouseLeave={e => (e.currentTarget.style.transform = "translateY(0)")}>
            ← Back to Risk Map
          </button>

          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ color: "#666" }}>Max stops/crew</span>
            <input value={maxStopsPerCrew} type="number" min={1} max={100}
              onChange={e => setMaxStopsPerCrew(Number(e.target.value))}
              style={{ width: 90, padding: "6px 8px", borderRadius: 10, border: "1px solid #ccc" }} />
          </div>

          <button onClick={buildPlan} disabled={loading || !items.length || !tsPrediction}
            style={{ padding: "8px 12px", borderRadius: 10, border: "1px solid #ccc", background: "white", cursor: "pointer", fontWeight: 700 }}>
            Re-generate Plan
          </button>

          <button onClick={exportPDF} disabled={!plan || loading}
            style={{ padding: "8px 14px", borderRadius: 10, border: "1px solid #2ecc71", background: "#f0fdf4", color: "#1a7a3a", cursor: "pointer", fontWeight: 700, opacity: !plan || loading ? 0.5 : 1 }}>
            ↓ Export PDF
          </button>
        </div>
      </div>

      <div style={{ marginTop: 12, display: "grid", gridTemplateColumns: "1fr 520px", gap: 12 }}>
        {/* Map */}
        <div style={{ borderRadius: 14, overflow: "hidden", border: "1px solid #e6e6e6" }}>
          <MapContainer center={mapCenter} zoom={13} style={{ height: 620, width: "100%" }}>
            <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
            {polylinePositions.length ? <Polyline positions={polylinePositions} pathOptions={{ weight: 5, opacity: 0.85 }} /> : null}
            {markers.map(m => (
              <Marker key={m.key} position={m.pos} icon={m.icon}>
                <Tooltip direction="top" offset={[0, -10]} opacity={1}>
                  <div style={{ fontWeight: 800 }}>{m.label}</div>
                </Tooltip>
              </Marker>
            ))}
          </MapContainer>
        </div>

        {/* Right panel */}
        <div style={{ borderRadius: 14, border: "1px solid #e6e6e6", padding: 12, height: 620, overflow: "auto" }}>
          <div style={{ fontSize: 16, fontWeight: 900 }}>Plan Summary</div>

          <div style={{ marginTop: 10, display: "grid", gap: 8, fontSize: 13 }}>
            {[
              ["Strategy", plan?.strategy || "—"],
              ["Total stops", plan?.totalStops ?? items.length],
              ["Recommended crews", plan?.recommendedCrewCount ?? crewCount],
              ["Total demand score", totalDemand.toFixed(3)],
              ["Depot", `${depot.name} (${depot.lat.toFixed(4)}, ${depot.lng.toFixed(4)})`],
            ].map(([label, value]) => (
              <div key={String(label)} style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#666" }}>{label}</span>
                <b style={{ maxWidth: 280, textAlign: "right" }}>{value}</b>
              </div>
            ))}
          </div>

          {/* Crew selector with per-crew resource summary */}
          <div style={{ marginTop: 14, borderTop: "1px solid #eee", paddingTop: 12 }}>
            <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 10, color: "#444" }}>
              All Crews — Resource Allocation
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {crewPlans.map(c => {
                const stops = safeArray<RouteStop>(c.stops).length;
                const isActive = c.crewNo === activeCrewNo;
                const emergencyCount = safeArray<RouteStop>(c.stops).filter(s => s.riskClass === "EMERGENCY").length;
                return (
                  <div
                    key={c.crewNo}
                    onClick={() => setActiveCrewNo(c.crewNo)}
                    style={{
                      border: isActive ? "2px solid #111" : "1px solid #ddd",
                      borderRadius: 10, padding: "10px 12px",
                      cursor: "pointer", background: isActive ? "#fafafa" : "#fff",
                      transition: "all 0.15s ease",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                      <span style={{ fontWeight: 800, fontSize: 14 }}>Crew {c.crewNo}</span>
                      <div style={{ display: "flex", gap: 6 }}>
                        {emergencyCount > 0 && (
                          <span style={{ background: "#fdf2f2", color: "#e74c3c", fontSize: 11, fontWeight: 700, padding: "2px 6px", borderRadius: 6 }}>
                            {emergencyCount} EMERGENCY
                          </span>
                        )}
                        <span style={{ background: "#f5f5f5", color: "#555", fontSize: 11, padding: "2px 6px", borderRadius: 6 }}>
                          {stops} stops
                        </span>
                      </div>
                    </div>

                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, fontSize: 12 }}>
                      <div>
                        <div style={{ color: "#888" }}>Trucks</div>
                        <div style={{ fontWeight: 900, fontSize: 16 }}>{c.trucksAllocated ?? 1}</div>
                        <LoadBar value={c.trucksAllocated ?? 1} max={maxTrucks} color="#3498db" />
                      </div>
                      <div>
                        <div style={{ color: "#888" }}>Workers</div>
                        <div style={{ fontWeight: 900, fontSize: 16 }}>{c.workersAllocated ?? 2}</div>
                        <LoadBar value={c.workersAllocated ?? 2} max={maxWorkers} color="#2ecc71" />
                      </div>
                      <div>
                        <div style={{ color: "#888" }}>Demand</div>
                        <div style={{ fontWeight: 900, fontSize: 16 }}>{(c.demandScore ?? 0).toFixed(1)}</div>
                        <LoadBar value={c.demandScore ?? 0} max={maxDemand} color="#e67e22" />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Route plan settings */}
          <div style={{ marginTop: 14, borderTop: "1px solid #eee", paddingTop: 14 }}>
            <div style={{ fontSize: 14, fontWeight: 900, marginBottom: 10 }}>Route Plan Settings</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div>
                <div style={{ fontSize: 12, color: "#666", marginBottom: 4 }}>Start Time</div>
                <div style={{ display: "flex", gap: 6 }}>
                  <input value={startHour} type="number" min={0} max={23}
                    onChange={e => setStartHour(Number(e.target.value))}
                    style={{ width: 70, padding: "6px 8px", borderRadius: 10, border: "1px solid #ccc" }} />
                  <input value={startMinute} type="number" min={0} max={59}
                    onChange={e => setStartMinute(Number(e.target.value))}
                    style={{ width: 70, padding: "6px 8px", borderRadius: 10, border: "1px solid #ccc" }} />
                </div>
              </div>
              <div>
                <div style={{ fontSize: 12, color: "#666", marginBottom: 4 }}>Service Minutes / Stop</div>
                <input value={serviceMinutesPerStop} type="number" min={1} max={120}
                  onChange={e => setServiceMinutesPerStop(Number(e.target.value))}
                  style={{ width: 100, padding: "6px 8px", borderRadius: 10, border: "1px solid #ccc" }} />
              </div>
            </div>
            <div style={{ marginTop: 8, fontSize: 12, color: "#777" }}>
              Schedule = OSRM travel time per leg + service time per stop.
            </div>
          </div>

          {/* Detailed route table */}
          <div style={{ marginTop: 14, borderTop: "1px solid #eee", paddingTop: 12 }}>
            <div style={{ fontSize: 14, fontWeight: 900 }}>Detailed Route Plan (Crew {activeCrewNo})</div>
            <div style={{ marginTop: 10, overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, background: "white" }}>
                <thead>
                  <tr style={{ textAlign: "left", borderBottom: "2px solid #eee", background: "#fafafa" }}>
                    {["Stop", "ETA", "Leg km", "Leg min", "Ward", "Risk", "Score", "Priority", "Reason", "Mode"].map(h => (
                      <th key={h} style={{ padding: "8px 6px", fontWeight: 700 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {scheduledRows.map(r => (
                    <tr key={`${r.stopLabel}-${r.ward}`} style={{ borderBottom: "1px solid #f2f2f2" }}>
                      <td style={{ padding: "7px 6px", fontWeight: 900 }}>{r.stopLabel}</td>
                      <td style={{ padding: "7px 6px" }}>{r.eta}</td>
                      <td style={{ padding: "7px 6px" }}>{r.legKm}</td>
                      <td style={{ padding: "7px 6px" }}>{r.legMin}</td>
                      <td style={{ padding: "7px 6px" }}>{r.ward}</td>
                      <td style={{ padding: "7px 6px", fontWeight: 900, color: r.risk === "EMERGENCY" ? "#e74c3c" : r.risk === "HIGH" ? "#e67e22" : "#333" }}>
                        {r.risk}
                      </td>
                      <td style={{ padding: "7px 6px" }}>{r.score}</td>
                      <td style={{ padding: "7px 6px" }}>{r.priority}</td>
                      <td style={{ padding: "7px 6px", color: "#666", fontSize: 11 }}>{r.reason}</td>
                      <td style={{ padding: "7px 6px", color: "#666", fontSize: 11 }}>{r.mode}</td>
                    </tr>
                  ))}
                  {!scheduledRows.length && (
                    <tr><td colSpan={10} style={{ padding: 12, color: "#777" }}>No route plan yet.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}