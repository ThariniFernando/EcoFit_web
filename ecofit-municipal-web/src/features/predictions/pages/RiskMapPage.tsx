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

import {
  fetchCurrentWeatherColombo,
  type CurrentWeatherResponse,
} from "../../weather/api/weatherApi";

const RISK_ORDER: Record<RiskClass, number> = {
  LOW: 0,
  MEDIUM: 1,
  HIGH: 2,
  EMERGENCY: 3,
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

function colorForRisk(r: RiskClass): string {
  switch (r) {
    case "LOW":
      return "#2ecc71";
    case "MEDIUM":
      return "#f1c40f";
    case "HIGH":
      return "#e67e22";
    case "EMERGENCY":
      return "#e74c3c";
    default:
      return "#3498db";
  }
}

function radiusForRisk(r: RiskClass): number {
  switch (r) {
    case "LOW":
      return 6;
    case "MEDIUM":
      return 8;
    case "HIGH":
      return 10;
    case "EMERGENCY":
      return 14;
    default:
      return 8;
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

export default function RiskMapPage() {
  const navigate = useNavigate();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [tsPrediction, setTsPrediction] = useState<string | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [items, setItems] = useState<PredictionMapItem[]>([]);

  // weather
  const [weather, setWeather] = useState<CurrentWeatherResponse | null>(null);
  const [weatherError, setWeatherError] = useState<string | null>(null);

  // filters
  const [query, setQuery] = useState("");
  const [riskEnabled, setRiskEnabled] = useState<Record<RiskClass, boolean>>({
    LOW: false,
    MEDIUM: false,
    HIGH: false,
    EMERGENCY: true,
  });

  const [showHoverLabels, setShowHoverLabels] = useState(true);
  const [alwaysShowEmergencyLabels, setAlwaysShowEmergencyLabels] =
    useState(true);

  const [selected, setSelected] = useState<PredictionMapItem | null>(null);
  const [flyTarget, setFlyTarget] = useState<{ lat: number; lng: number } | null>(
    null
  );

  // ✅ AUTO REFRESH predictions every 15s
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

    return () => {
      alive = false;
      clearInterval(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ✅ AUTO REFRESH weather every 10 minutes
  useEffect(() => {
    let alive = true;

    const loadWeather = async () => {
      try {
        setWeatherError(null);
        const w = await fetchCurrentWeatherColombo();
        if (!alive) return;
        setWeather(w);
      } catch (e: any) {
        if (!alive) return;
        setWeatherError(e?.message || "Failed to load weather");
      }
    };

    loadWeather();
    const t = setInterval(loadWeather, 10 * 60 * 1000);

    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();

    return (items || [])
      .filter((x) => typeof x.lat === "number" && typeof x.lng === "number")
      .filter((x) => riskEnabled[x.riskClass])
      .filter((x) => {
        if (!q) return true;
        const name = (x.wardName || "").toLowerCase();
        const id = (x.wardId || "").toLowerCase();
        return name.includes(q) || id.includes(q);
      })
      .sort((a, b) => {
        const ra = RISK_ORDER[a.riskClass] ?? 0;
        const rb = RISK_ORDER[b.riskClass] ?? 0;
        if (rb !== ra) return rb - ra;
        return (b.riskScore || 0) - (a.riskScore || 0);
      });
  }, [items, query, riskEnabled]);

  const mapCenter = useMemo(() => {
    return { lat: 6.9271, lng: 79.8612 };
  }, []);

  const showing = filtered.length;

  const queueItems = useMemo(() => filtered.slice(0, 200), [filtered]);

  const goActionPlan = () => {
    navigate("/action-plan", {
      state: {
        tsPrediction,
        items: filtered.map((x) => ({
          wardId: x.wardId,
          wardName: x.wardName,
          lat: x.lat,
          lng: x.lng,
          riskClass: x.riskClass,
          riskScore: x.riskScore,
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
          Generate Action Plan →
        </button>
      </div>

      <div style={{ marginTop: 12, display: "flex", gap: 10, flexWrap: "wrap" }}>
        <button
          style={filterBtn}
          onMouseEnter={(e) => Object.assign(e.currentTarget.style, buttonHover)}
          onMouseLeave={(e) => Object.assign(e.currentTarget.style, filterBtn)}
          onClick={() =>
            setRiskEnabled({
              LOW: true,
              MEDIUM: true,
              HIGH: true,
              EMERGENCY: true,
            })
          }
        >
          Show All
        </button>
        <button
          style={filterBtn}
          onMouseEnter={(e) => Object.assign(e.currentTarget.style, buttonHover)}
          onMouseLeave={(e) => Object.assign(e.currentTarget.style, filterBtn)}
          onClick={() =>
            setRiskEnabled({
              LOW: false,
              MEDIUM: false,
              HIGH: true,
              EMERGENCY: true,
            })
          }
        >
          High+
        </button>
        <button
          style={filterBtn}
          onMouseEnter={(e) => Object.assign(e.currentTarget.style, buttonHover)}
          onMouseLeave={(e) => Object.assign(e.currentTarget.style, filterBtn)}
          onClick={() =>
            setRiskEnabled({
              LOW: false,
              MEDIUM: false,
              HIGH: false,
              EMERGENCY: true,
            })
          }
        >
          Emergency
        </button>

        <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={riskEnabled.LOW}
            onChange={(e) =>
              setRiskEnabled((p) => ({ ...p, LOW: e.target.checked }))
            }
          />
          {/* <span style={{ color: colorForRisk("LOW"), fontWeight: 700 }}>LOW</span> */}
          <span
            style={{
              background: colorForRisk("LOW"),
              color: "white",
              padding: "3px 8px",
              borderRadius: 8,
              fontSize: 12,
              fontWeight: 700,
            }}
          >
            LOW
          </span>
        </label>

        <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <input
            type="checkbox"
            checked={riskEnabled.MEDIUM}
            onChange={(e) =>
              setRiskEnabled((p) => ({ ...p, MEDIUM: e.target.checked }))
            }
          />
          {/* <span style={{ color: colorForRisk("MEDIUM"), fontWeight: 700 }}>
            MEDIUM
          </span> */}
          <span
            style={{
              background: colorForRisk("MEDIUM"),
              color: "white",
              padding: "3px 8px",
              borderRadius: 8,
              fontSize: 12,
              fontWeight: 700,
            }}
          >
            MEDIUM
          </span>
        </label>

        <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <input
            type="checkbox"
            checked={riskEnabled.HIGH}
            onChange={(e) =>
              setRiskEnabled((p) => ({ ...p, HIGH: e.target.checked }))
            }
          />
          {/* <span style={{ color: colorForRisk("HIGH"), fontWeight: 700 }}>HIGH</span> */}
          <span
            style={{
              background: colorForRisk("HIGH"),
              color: "white",
              padding: "3px 8px",
              borderRadius: 8,
              fontSize: 12,
              fontWeight: 700,
            }}
          >
            HIGH
          </span>
        </label>

        <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <input
            type="checkbox"
            checked={riskEnabled.EMERGENCY}
            onChange={(e) =>
              setRiskEnabled((p) => ({ ...p, EMERGENCY: e.target.checked }))
            }
          />
          {/* <span style={{ color: colorForRisk("EMERGENCY"), fontWeight: 700 }}>
            EMERGENCY
          </span> */}
          <span
            style={{
              background: colorForRisk("EMERGENCY"),
              color: "white",
              padding: "3px 8px",
              borderRadius: 8,
              fontSize: 12,
              fontWeight: 700,
            }}
          >
            EMERGENCY
          </span>
        </label>

        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search ward name or ID..."
          style={{
            padding: "8px 12px",
            borderRadius: 20,
            border: "1px solid #ddd",
            minWidth: 260,
            outline: "none",
            boxShadow: "0 1px 4px rgba(0,0,0,.06)"
          }}
        />

        <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <input
            type="checkbox"
            checked={showHoverLabels}
            onChange={(e) => setShowHoverLabels(e.target.checked)}
          />
          Hover labels
        </label>

        <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <input
            type="checkbox"
            checked={alwaysShowEmergencyLabels}
            onChange={(e) => setAlwaysShowEmergencyLabels(e.target.checked)}
          />
          Always show EMERGENCY labels
        </label>
      </div>

      <div
        style={{
          marginTop: 12,
          display: "grid",
          gridTemplateColumns: "1fr 360px",
          gap: 12,
        }}
      >
        <div
          style={{
            border: "1px solid #e5e5e5",
            borderRadius: 12,
            overflow: "hidden",
            boxShadow: "0 4px 12px rgba(0,0,0,.05)"
          }}
        >
          <MapContainer
            center={[mapCenter.lat, mapCenter.lng]}
            zoom={11}
            style={{ height: 560, width: "100%" }}
          >
            <TileLayer
              attribution="&copy; OpenStreetMap contributors"
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />

            <FlyTo target={flyTarget} />

            {filtered.map((p) => {
              const lat = p.lat as number;
              const lng = p.lng as number;

              const label = `${p.wardName || p.wardId} — ${p.riskClass} (${p.riskScore.toFixed(
                3
              )})`;

              const forceLabel =
                alwaysShowEmergencyLabels && p.riskClass === "EMERGENCY";

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
                  eventHandlers={{
                    click: () => {
                      setSelected(p);
                      setFlyTarget({ lat, lng });
                    },
                  }}
                >
                  {(showHoverLabels || forceLabel) && (
                    <Tooltip
                      permanent={forceLabel}
                      direction="top"
                      offset={[0, -8]}
                    >
                      {label}
                    </Tooltip>
                  )}
                </CircleMarker>
              );
            })}
          </MapContainer>
        </div>

        <div
          style={{
            border: "1px solid #e5e5e5",
            borderRadius: 12,
            padding: 12,
            height: 560,
            overflow: "auto",
          }}
        >
          {/* <h3 style={{ marginTop: 0 }}>Queue (priority list)</h3> */}
          <div style={{ fontWeight: 800, fontSize: 16, marginBottom: 10 }}>Priority Queue</div>

          <div
            style={{
              border: "1px solid #eee",
              borderRadius: 12,
              padding: 12,
              marginBottom: 12,
              cursor: "pointer",
              background: "#f9fbff",
            }}
          >
            <div style={{ fontWeight: 700, marginBottom: 6 }}>Weather</div>
            {weather ? (
              <div style={{ fontSize: 13, opacity: 0.85, lineHeight: 1.5 }}>
                <div>
                  <b>{weather.condition || "—"}</b>
                </div>
                <div>
                  Temp: {weather.tempC ?? "—"}°C | Humidity:{" "}
                  {weather.humidity ?? "—"}%
                </div>
                <div>
                  Wind: {weather.windKph ?? "—"} kph
                </div>
                <div style={{ fontSize: 12, opacity: 0.7 }}>
                  Observed: {weather.observedAt || "—"}
                </div>
              </div>
            ) : (
              <div style={{ fontSize: 13, opacity: 0.8 }}>
                {weatherError ? weatherError : "Loading weather..."}
              </div>
            )}
          </div>

          <div style={{ opacity: 0.8, marginBottom: 10 }}>
            Click a row to zoom.
          </div>

          {queueItems.map((w) => (
            <div
              key={w._id}
              onClick={() => {
                if (typeof w.lat === "number" && typeof w.lng === "number") {
                  setSelected(w);
                  setFlyTarget({ lat: w.lat, lng: w.lng });
                }
              }}
              style={{
                border: "2px solid #eee",
                borderRadius: 12,
                padding: 10,
                marginBottom: 8,
                cursor: "pointer",
                background: "#fff",
                transition: "all 0.2s ease",
              }}
            >
              <div style={{ fontWeight: 700 }}>{w.wardName || w.wardId}</div>
              <div style={{ fontSize: 13, opacity: 0.8 }}>
                {w.riskClass} | score {w.riskScore.toFixed(3)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}