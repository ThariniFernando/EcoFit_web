import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Tooltip,
  useMap,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";

import QuickNav from "../../../app/layout/QuickNav";
import {
  fetchLatestPredictions,
  type PredictionMapItem,
  type RiskClass,
} from "../api/predictionsApi";
import { apiClient } from "../../../lib/apiClient";

const RISK_ORDER: Record<RiskClass, number> = {
  LOW: 0, MEDIUM: 1, HIGH: 2, EMERGENCY: 3,
};

const filterBtn = {
  padding: "6px 12px",
  borderRadius: 20,
  border: "1px solid #ddd",
  background: "#fff",
  cursor: "pointer",
  fontSize: 13,
  fontWeight: 600,
};

const RISK_COLORS: Record<string, string> = {
  EMERGENCY: "#e74c3c",
  HIGH: "#e67e22",
  MEDIUM: "#f1c40f",
  LOW: "#2ecc71",
};

function colorForRisk(r: RiskClass): string {
  return RISK_COLORS[r] || "#3498db";
}

function radiusForRisk(r: RiskClass): number {
  switch (r) {
    case "LOW": return 6;
    case "MEDIUM": return 8;
    case "HIGH": return 10;
    case "EMERGENCY": return 14;
    default: return 8;
  }
}

function FlyTo({ target }: { target: { lat: number; lng: number } | null }) {
  const map = useMap();
  useEffect(() => {
    if (!target) return;
    map.flyTo([target.lat, target.lng], 13, { duration: 0.7 });
  }, [target, map]);
  return null;
}

// Simple inline bar chart for risk history
type HistoryItem = {
  tsPrediction: string;
  riskClass: string;
  riskScore: number;
};

function RiskHistoryChart({ history }: { history: HistoryItem[] }) {
  if (!history.length) {
    return <div style={{ color: "#aaa", fontSize: 13, padding: "12px 0" }}>No history data</div>;
  }

  // Deduplicate by date (keep last per day)
  const byDay = new Map<string, HistoryItem>();
  for (const h of history) {
    const day = h.tsPrediction.slice(0, 10);
    byDay.set(day, h);
  }
  const dedupedHistory = Array.from(byDay.values()).slice(-14); // last 14 days

  return (
    <div>
      <div style={{ fontSize: 11, color: "#aaa", marginBottom: 6 }}>
        Risk score history (last {dedupedHistory.length} data points)
      </div>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 3, height: 60 }}>
        {dedupedHistory.map((h, i) => {
          const height = Math.max(4, Math.round(h.riskScore * 56));
          return (
            <div
              key={i}
              title={`${h.tsPrediction.slice(0, 10)} — ${h.riskClass} (${h.riskScore.toFixed(2)})`}
              style={{
                flex: 1,
                height,
                background: RISK_COLORS[h.riskClass] || "#ccc",
                borderRadius: "2px 2px 0 0",
                opacity: 0.85,
                transition: "height 0.3s ease",
                cursor: "default",
              }}
            />
          );
        })}
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "#bbb", marginTop: 4 }}>
        <span>{dedupedHistory[0]?.tsPrediction.slice(0, 10)}</span>
        <span>{dedupedHistory[dedupedHistory.length - 1]?.tsPrediction.slice(0, 10)}</span>
      </div>

      {/* Legend */}
      <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
        {Object.entries(RISK_COLORS).map(([rc, color]) => (
          <div key={rc} style={{ display: "flex", alignItems: "center", gap: 3, fontSize: 10 }}>
            <div style={{ width: 8, height: 8, borderRadius: 2, background: color }} />
            <span style={{ color: "#888" }}>{rc}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// Ward detail panel shown when a ward is selected
function WardDetailPanel({
  ward,
  onClose,
}: {
  ward: PredictionMapItem;
  onClose: () => void;
}) {
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  useEffect(() => {
    if (!ward) return;
    setLoadingHistory(true);
    apiClient
      .get(`/api/v1/predictions/history/${ward.wardId}`, { params: { limit: 50 } })
      .then((res) => setHistory(res.data?.history || []))
      .catch(() => setHistory([]))
      .finally(() => setLoadingHistory(false));
  }, [ward.wardId]);

  const probs = Array.isArray(ward.probabilities) ? ward.probabilities : [];
  const labels = ["LOW", "MEDIUM", "HIGH", "EMERGENCY"];

  return (
    <div
      style={{
        border: "1px solid #e5e5e5",
        borderRadius: 12,
        padding: 16,
        height: 560,
        overflow: "auto",
        background: "#fff",
        boxShadow: "0 4px 12px rgba(0,0,0,.08)",
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
        <div>
          <div style={{ fontWeight: 800, fontSize: 16 }}>{ward.wardName || ward.wardId}</div>
          <div style={{ fontSize: 12, color: "#aaa", marginTop: 2 }}>{ward.wardId}</div>
        </div>
        <button
          onClick={onClose}
          style={{
            border: "none", background: "#f5f5f5", borderRadius: 8,
            padding: "4px 10px", cursor: "pointer", fontSize: 13, color: "#888",
          }}
        >
          ✕
        </button>
      </div>

      {/* Current risk */}
      <div
        style={{
          background: RISK_COLORS[ward.riskClass] + "18",
          border: `1.5px solid ${RISK_COLORS[ward.riskClass]}`,
          borderRadius: 10,
          padding: "10px 14px",
          marginBottom: 14,
        }}
      >
        <div style={{ fontSize: 11, color: "#888", fontWeight: 600 }}>Current risk</div>
        <div style={{ fontWeight: 800, fontSize: 22, color: RISK_COLORS[ward.riskClass] }}>
          {ward.riskClass}
        </div>
        <div style={{ fontSize: 12, color: "#aaa" }}>Score: {ward.riskScore.toFixed(4)}</div>
      </div>

      {/* Probability breakdown */}
      {probs.length === 4 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 8 }}>Class probabilities</div>
          {labels.map((label, i) => {
            const pct = Math.round((probs[i] || 0) * 100);
            return (
              <div key={label} style={{ marginBottom: 6 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 2 }}>
                  <span style={{ fontWeight: 600, color: RISK_COLORS[label] }}>{label}</span>
                  <span style={{ color: "#888" }}>{pct}%</span>
                </div>
                <div style={{ background: "#f0f0f0", borderRadius: 4, height: 6, overflow: "hidden" }}>
                  <div
                    style={{
                      width: `${pct}%`,
                      background: RISK_COLORS[label],
                      height: "100%",
                      borderRadius: 4,
                      transition: "width 0.4s ease",
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* History chart */}
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 8 }}>Risk score history</div>
        {loadingHistory ? (
          <div style={{ color: "#aaa", fontSize: 12 }}>Loading history...</div>
        ) : (
          <RiskHistoryChart history={history} />
        )}
      </div>

      {/* Location */}
      <div style={{ fontSize: 12, color: "#aaa", marginTop: 8 }}>
        📍 {ward.lat?.toFixed(4)}, {ward.lng?.toFixed(4)}
      </div>
    </div>
  );
}

export default function RiskMapPage() {
  const navigate = useNavigate();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tsPrediction, setTsPrediction] = useState<string | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [items, setItems] = useState<PredictionMapItem[]>([]);

  const [query, setQuery] = useState("");
  const [riskEnabled, setRiskEnabled] = useState<Record<RiskClass, boolean>>({
    LOW: false, MEDIUM: false, HIGH: false, EMERGENCY: true,
  });
  const [showHoverLabels, setShowHoverLabels] = useState(true);
  const [alwaysShowEmergencyLabels, setAlwaysShowEmergencyLabels] = useState(true);
  const [selected, setSelected] = useState<PredictionMapItem | null>(null);
  const [flyTarget, setFlyTarget] = useState<{ lat: number; lng: number } | null>(null);
  const [showDetail, setShowDetail] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        setError(null);
        setLoading(true);
        const data = await fetchLatestPredictions(1000);
        if (!alive) return;
        if (!tsPrediction || data.tsPrediction !== tsPrediction) {
          setTsPrediction(data.tsPrediction);
          setCounts(data.counts || {});
          setItems(data.items || []);
        }
      } catch (e: any) {
        if (!alive) return;
        setError(e?.message || "Failed to load predictions");
      } finally {
        if (!alive) return;
        setLoading(false);
      }
    };
    load();
    const t = setInterval(load, 15000);
    return () => { alive = false; clearInterval(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (items || [])
      .filter((x) => typeof x.lat === "number" && typeof x.lng === "number")
      .filter((x) => riskEnabled[x.riskClass])
      .filter((x) => {
        if (!q) return true;
        return (x.wardName || "").toLowerCase().includes(q) ||
          (x.wardId || "").toLowerCase().includes(q);
      })
      .sort((a, b) => {
        const ra = RISK_ORDER[a.riskClass] ?? 0;
        const rb = RISK_ORDER[b.riskClass] ?? 0;
        if (rb !== ra) return rb - ra;
        return (b.riskScore || 0) - (a.riskScore || 0);
      });
  }, [items, query, riskEnabled]);

  const mapCenter = useMemo(() => ({ lat: 6.9271, lng: 79.8612 }), []);
  const showing = filtered.length;
  const queueItems = useMemo(() => filtered.slice(0, 200), [filtered]);

  const handleSelectWard = (p: PredictionMapItem) => {
    setSelected(p);
    setShowDetail(true);
    if (typeof p.lat === "number" && typeof p.lng === "number") {
      setFlyTarget({ lat: p.lat as number, lng: p.lng as number });
    }
  };

  const goActionPlan = () => {
    navigate("/action-plan", {
      state: {
        tsPrediction,
        items: filtered.map((x) => ({
          wardId: x.wardId, wardName: x.wardName,
          lat: x.lat, lng: x.lng,
          riskClass: x.riskClass, riskScore: x.riskScore,
        })),
      },
    });
  };

  const buttonHover = { background: "#f0f0f0", transform: "translateY(-1px)" };

  return (
    <div style={{ padding: 16 }}>
      <QuickNav />

      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 8 }}>
        <div>
          <h2 style={{ margin: 0 }}>Ward Risk Map</h2>
          <div style={{ opacity: 0.8, marginTop: 6 }}>
            Prediction Time: <b>{tsPrediction || "—"}</b> | Total{" "}
            <b>{counts?.TOTAL ?? items.length ?? 0}</b> | Showing <b>{showing}</b>
            {loading ? " | loading..." : ""}
            {error ? ` | ${error}` : ""}
          </div>
        </div>
        <button
          onClick={goActionPlan}
          style={{
            padding: "10px 16px", borderRadius: 12, border: "none",
            background: "rgb(45 106 79)", color: "white", fontWeight: 700,
            cursor: "pointer", height: 40, boxShadow: "0 2px 6px rgba(0,0,0,.15)",
            alignSelf: "flex-start", transition: "all 0.2s ease",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.transform = "translateY(-2px)")}
          onMouseLeave={(e) => (e.currentTarget.style.transform = "translateY(0)")}
        >
          Generate Action Plan →
        </button>
      </div>

      <div style={{ marginTop: 12, display: "flex", gap: 10, flexWrap: "wrap" }}>
        <button style={filterBtn}
          onMouseEnter={(e) => Object.assign(e.currentTarget.style, buttonHover)}
          onMouseLeave={(e) => Object.assign(e.currentTarget.style, filterBtn)}
          onClick={() => setRiskEnabled({ LOW: true, MEDIUM: true, HIGH: true, EMERGENCY: true })}
        >Show All</button>
        <button style={filterBtn}
          onMouseEnter={(e) => Object.assign(e.currentTarget.style, buttonHover)}
          onMouseLeave={(e) => Object.assign(e.currentTarget.style, filterBtn)}
          onClick={() => setRiskEnabled({ LOW: false, MEDIUM: false, HIGH: true, EMERGENCY: true })}
        >High+</button>
        <button style={filterBtn}
          onMouseEnter={(e) => Object.assign(e.currentTarget.style, buttonHover)}
          onMouseLeave={(e) => Object.assign(e.currentTarget.style, filterBtn)}
          onClick={() => setRiskEnabled({ LOW: false, MEDIUM: false, HIGH: false, EMERGENCY: true })}
        >Emergency</button>

        {(["LOW", "MEDIUM", "HIGH", "EMERGENCY"] as RiskClass[]).map((rc) => (
          <label key={rc} style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
            <input type="checkbox" checked={riskEnabled[rc]}
              onChange={(e) => setRiskEnabled((p) => ({ ...p, [rc]: e.target.checked }))} />
            <span style={{ background: colorForRisk(rc), color: "white", padding: "3px 8px", borderRadius: 8, fontSize: 12, fontWeight: 700 }}>
              {rc}
            </span>
          </label>
        ))}

        <input value={query} onChange={(e) => setQuery(e.target.value)}
          placeholder="Search ward name or ID..."
          style={{ padding: "8px 12px", borderRadius: 20, border: "1px solid #ddd", minWidth: 260, outline: "none", boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}
        />

        <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <input type="checkbox" checked={showHoverLabels}
            onChange={(e) => setShowHoverLabels(e.target.checked)} />
          Hover labels
        </label>

        <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <input type="checkbox" checked={alwaysShowEmergencyLabels}
            onChange={(e) => setAlwaysShowEmergencyLabels(e.target.checked)} />
          Always show EMERGENCY labels
        </label>
      </div>

      <div style={{ marginTop: 12, display: "grid", gridTemplateColumns: showDetail ? "1fr 380px" : "1fr 360px", gap: 12 }}>
        {/* Map */}
        <div style={{ border: "1px solid #e5e5e5", borderRadius: 12, overflow: "hidden", boxShadow: "0 4px 12px rgba(0,0,0,.05)" }}>
          <MapContainer center={[mapCenter.lat, mapCenter.lng]} zoom={11} style={{ height: 560, width: "100%" }}>
            <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
            <FlyTo target={flyTarget} />
            {filtered.map((p) => {
              const lat = p.lat as number;
              const lng = p.lng as number;
              const label = `${p.wardName || p.wardId} — ${p.riskClass} (${p.riskScore.toFixed(3)})`;
              const forceLabel = alwaysShowEmergencyLabels && p.riskClass === "EMERGENCY";
              return (
                <CircleMarker
                  key={p._id}
                  center={[lat, lng]}
                  radius={radiusForRisk(p.riskClass)}
                  pathOptions={{
                    color: colorForRisk(p.riskClass),
                    fillColor: colorForRisk(p.riskClass),
                    fillOpacity: 0.55,
                    weight: selected?._id === p._id ? 3 : 1,
                  }}
                  eventHandlers={{ click: () => handleSelectWard(p) }}
                >
                  {(showHoverLabels || forceLabel) && (
                    <Tooltip permanent={forceLabel} direction="top" offset={[0, -8]}>
                      {label}
                    </Tooltip>
                  )}
                </CircleMarker>
              );
            })}
          </MapContainer>
        </div>

        {/* Right panel — detail or priority queue */}
        {showDetail && selected ? (
          <WardDetailPanel
            ward={selected}
            onClose={() => setShowDetail(false)}
          />
        ) : (
          <div style={{ border: "1px solid #e5e5e5", borderRadius: 12, padding: 12, height: 560, overflow: "auto" }}>
            <div style={{ fontWeight: 800, fontSize: 16, marginBottom: 10 }}>Priority Queue</div>
            <div style={{ opacity: 0.8, marginBottom: 10 }}>Click a ward to see details.</div>
            {queueItems.map((w) => (
              <div
                key={w._id}
                onClick={() => handleSelectWard(w)}
                style={{
                  border: `2px solid ${selected?._id === w._id ? colorForRisk(w.riskClass) : "#eee"}`,
                  borderRadius: 12, padding: 10, marginBottom: 8,
                  cursor: "pointer", background: "#fff", transition: "all 0.2s ease",
                }}
              >
                <div style={{ fontWeight: 700 }}>{w.wardName || w.wardId}</div>
                <div style={{ fontSize: 13, opacity: 0.8 }}>
                  <span style={{ color: colorForRisk(w.riskClass), fontWeight: 700 }}>{w.riskClass}</span>
                  {" | score "}{w.riskScore.toFixed(3)}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}