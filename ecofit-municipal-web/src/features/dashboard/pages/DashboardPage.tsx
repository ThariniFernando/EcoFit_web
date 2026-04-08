import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import QuickNav from "../../../app/layout/QuickNav";
import { fetchDashboardStats, type DashboardStats } from "../api/dashboardApi";

const RISK_COLORS: Record<string, string> = {
  EMERGENCY: "#e74c3c",
  HIGH: "#e67e22",
  MEDIUM: "#f1c40f",
  LOW: "#2ecc71",
};

const RISK_BG: Record<string, string> = {
  EMERGENCY: "#fdf2f2",
  HIGH: "#fef9f0",
  MEDIUM: "#fefdf0",
  LOW: "#f0fdf4",
};

function StatCard({
  title,
  value,
  subtitle,
  color,
  bg,
  onClick,
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  color?: string;
  bg?: string;
  onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      style={{
        background: bg || "#fff",
        border: `1.5px solid ${color || "#e5e5e5"}`,
        borderRadius: 16,
        padding: "20px 24px",
        cursor: onClick ? "pointer" : "default",
        transition: "transform 0.15s ease, box-shadow 0.15s ease",
        boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
      }}
      onMouseEnter={(e) => {
        if (onClick) {
          e.currentTarget.style.transform = "translateY(-2px)";
          e.currentTarget.style.boxShadow = "0 6px 16px rgba(0,0,0,0.1)";
        }
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = "translateY(0)";
        e.currentTarget.style.boxShadow = "0 2px 8px rgba(0,0,0,0.06)";
      }}
    >
      <div style={{ fontSize: 13, color: "#888", fontWeight: 600, marginBottom: 6 }}>
        {title}
      </div>
      <div style={{ fontSize: 36, fontWeight: 800, color: color || "#222", lineHeight: 1 }}>
        {value}
      </div>
      {subtitle && (
        <div style={{ fontSize: 12, color: "#aaa", marginTop: 6 }}>{subtitle}</div>
      )}
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontWeight: 700, fontSize: 16, color: "#333", marginBottom: 12, marginTop: 28 }}>
      {children}
    </div>
  );
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const load = async () => {
    try {
      setError(null);
      const data = await fetchDashboardStats();
      setStats(data);
      setLastUpdated(new Date());
    } catch (e: any) {
      setError(e?.message || "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, []);

  const collectionRate =
    stats && stats.serviceLogs.total > 0
      ? Math.round((stats.serviceLogs.collected / stats.serviceLogs.total) * 100)
      : 0;

  return (
    <div style={{ padding: 16, maxWidth: 1200, margin: "0 auto" }}>
      <QuickNav />

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 24, fontWeight: 800 }}>Operations Dashboard</h2>
          <div style={{ color: "#888", fontSize: 13, marginTop: 4 }}>
            {lastUpdated ? `Last updated: ${lastUpdated.toLocaleTimeString()}` : "Loading..."}
            {" · "}
            {stats?.tsPrediction ? `Prediction: ${new Date(stats.tsPrediction).toLocaleString()}` : ""}
          </div>
        </div>
        <button
          onClick={load}
          disabled={loading}
          style={{
            padding: "8px 18px",
            borderRadius: 10,
            border: "1px solid #ddd",
            background: "#fff",
            cursor: "pointer",
            fontWeight: 600,
            fontSize: 13,
          }}
        >
          {loading ? "Refreshing..." : "↻ Refresh"}
        </button>
      </div>

      {error && (
        <div style={{ background: "#fdf2f2", border: "1px solid #f5c6cb", borderRadius: 10, padding: 12, color: "#c0392b", marginBottom: 16 }}>
          {error}
        </div>
      )}

      <SectionTitle>Ward Risk Overview</SectionTitle>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        {(["EMERGENCY", "HIGH", "MEDIUM", "LOW"] as const).map((rc) => (
          <StatCard
            key={rc}
            title={rc}
            value={stats?.riskCounts[rc] ?? "—"}
            subtitle={`of ${stats?.riskCounts.TOTAL ?? 0} total wards`}
            color={RISK_COLORS[rc]}
            bg={RISK_BG[rc]}
            onClick={() => navigate("/risk-map")}
          />
        ))}
      </div>

      <SectionTitle>This Week at a Glance</SectionTitle>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
        <StatCard
          title="Open Alerts"
          value={stats?.openAlerts ?? "—"}
          subtitle="Unresolved emergency alerts"
          color={stats?.openAlerts ? "#e74c3c" : "#2ecc71"}
          bg={stats?.openAlerts ? "#fdf2f2" : "#f0fdf4"}
          onClick={() => navigate("/risk-map")}
        />
        <StatCard
          title="Total Complaints"
          value={stats?.complaints.total ?? "—"}
          subtitle="Last 7 days"
          color="#3498db"
          bg="#f0f8ff"
          onClick={() => navigate("/complaints")}
        />
        <StatCard
          title="Collection Rate"
          value={`${collectionRate}%`}
          subtitle={`${stats?.serviceLogs.collected ?? 0} collected of ${stats?.serviceLogs.total ?? 0} trips`}
          color={collectionRate >= 80 ? "#2ecc71" : collectionRate >= 60 ? "#e67e22" : "#e74c3c"}
          bg={collectionRate >= 80 ? "#f0fdf4" : collectionRate >= 60 ? "#fef9f0" : "#fdf2f2"}
          onClick={() => navigate("/service-logs")}
        />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 16 }}>
        <div style={{ background: "#fff", border: "1px solid #e5e5e5", borderRadius: 16, padding: 20, boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
          <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 16 }}>Complaints Breakdown</div>
          {[
            { label: "New", value: stats?.complaints.NEW ?? 0, color: "#e74c3c" },
            { label: "In Progress", value: stats?.complaints.IN_PROGRESS ?? 0, color: "#e67e22" },
            { label: "Resolved", value: stats?.complaints.RESOLVED ?? 0, color: "#2ecc71" },
            { label: "Rejected", value: stats?.complaints.REJECTED ?? 0, color: "#95a5a6" },
          ].map((item) => {
            const total = stats?.complaints.total || 1;
            const pct = Math.round((item.value / total) * 100);
            return (
              <div key={item.label} style={{ marginBottom: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 4 }}>
                  <span style={{ fontWeight: 600 }}>{item.label}</span>
                  <span style={{ color: "#888" }}>{item.value} ({pct}%)</span>
                </div>
                <div style={{ background: "#f0f0f0", borderRadius: 6, height: 8, overflow: "hidden" }}>
                  <div style={{ width: `${pct}%`, background: item.color, height: "100%", borderRadius: 6, transition: "width 0.5s ease" }} />
                </div>
              </div>
            );
          })}
        </div>

        <div style={{ background: "#fff", border: "1px solid #e5e5e5", borderRadius: 16, padding: 20, boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
          <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 16 }}>Service Performance (7 days)</div>
          {[
            { label: "Collected", value: stats?.serviceLogs.collected ?? 0, color: "#2ecc71" },
            { label: "Missed", value: stats?.serviceLogs.missed ?? 0, color: "#e74c3c" },
            { label: "Partial", value: stats?.serviceLogs.partial ?? 0, color: "#e67e22" },
          ].map((item) => {
            const total = stats?.serviceLogs.total || 1;
            const pct = Math.round((item.value / total) * 100);
            return (
              <div key={item.label} style={{ marginBottom: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 4 }}>
                  <span style={{ fontWeight: 600 }}>{item.label}</span>
                  <span style={{ color: "#888" }}>{item.value} ({pct}%)</span>
                </div>
                <div style={{ background: "#f0f0f0", borderRadius: 6, height: 8, overflow: "hidden" }}>
                  <div style={{ width: `${pct}%`, background: item.color, height: "100%", borderRadius: 6, transition: "width 0.5s ease" }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <SectionTitle>Top 5 Highest Risk Wards</SectionTitle>
      <div style={{ background: "#fff", border: "1px solid #e5e5e5", borderRadius: 16, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "#f8f8f8" }}>
              <th style={{ padding: "12px 16px", textAlign: "left", fontSize: 13, fontWeight: 600, color: "#888" }}>Rank</th>
              <th style={{ padding: "12px 16px", textAlign: "left", fontSize: 13, fontWeight: 600, color: "#888" }}>Ward</th>
              <th style={{ padding: "12px 16px", textAlign: "left", fontSize: 13, fontWeight: 600, color: "#888" }}>Risk Class</th>
              <th style={{ padding: "12px 16px", textAlign: "right", fontSize: 13, fontWeight: 600, color: "#888" }}>Risk Score</th>
            </tr>
          </thead>
          <tbody>
            {(stats?.topRiskWards || []).map((w, i) => (
              <tr
                key={w.wardId}
                style={{ borderTop: "1px solid #f0f0f0", cursor: "pointer" }}
                onClick={() => navigate("/risk-map")}
                onMouseEnter={(e) => (e.currentTarget.style.background = "#fafafa")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              >
                <td style={{ padding: "12px 16px", fontWeight: 700, color: "#aaa" }}>#{i + 1}</td>
                <td style={{ padding: "12px 16px", fontWeight: 600 }}>{w.wardName}</td>
                <td style={{ padding: "12px 16px" }}>
                  <span style={{
                    background: RISK_BG[w.riskClass] || "#f5f5f5",
                    color: RISK_COLORS[w.riskClass] || "#333",
                    padding: "3px 10px",
                    borderRadius: 8,
                    fontSize: 12,
                    fontWeight: 700,
                  }}>
                    {w.riskClass}
                  </span>
                </td>
                <td style={{ padding: "12px 16px", textAlign: "right", fontWeight: 700, color: RISK_COLORS[w.riskClass] || "#333" }}>
                  {w.riskScore.toFixed(3)}
                </td>
              </tr>
            ))}
            {!stats?.topRiskWards?.length && (
              <tr>
                <td colSpan={4} style={{ padding: 24, textAlign: "center", color: "#aaa" }}>
                  {loading ? "Loading..." : "No prediction data available"}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}