import { NavLink } from "react-router-dom";

function linkStyle(isActive: boolean): React.CSSProperties {
  return {
    display: "block",
    padding: "12px 14px",
    borderRadius: 10,
    border: "1px solid #ddd",
    background: isActive ? "#f3f4f6" : "#fff",
    color: "#111",
    fontWeight: 700,
    textDecoration: "none",
  };
}

export default function Sidebar() {
  return (
    <div
      style={{
        width: 240,
        border: "1px solid #e5e5e5",
        borderRadius: 12,
        padding: 12,
        background: "#fff",
      }}
    >
      <div style={{ fontSize: 12, fontWeight: 800, opacity: 0.7, marginBottom: 10 }}>
        MENU
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <NavLink to="/risk-map" style={({ isActive }) => linkStyle(isActive)}>
          Risk Map
        </NavLink>

        <NavLink to="/action-plan" style={({ isActive }) => linkStyle(isActive)}>
          Action Plan
        </NavLink>

        <NavLink to="/service-logs" style={({ isActive }) => linkStyle(isActive)}>
          Service Logs
        </NavLink>

        <NavLink to="/complaints" style={({ isActive }) => linkStyle(isActive)}>
          Complaints
        </NavLink>

        <NavLink to="/ward-hourly-features" style={({ isActive }) => linkStyle(isActive)}>
          Ward Hourly Features
        </NavLink>

        <NavLink to="/weather-hourly" style={({ isActive }) => linkStyle(isActive)}>
          Weather Hourly
        </NavLink>

        <NavLink to="/knowledge-base" style={({ isActive }) => linkStyle(isActive)}>
          Knowledge Base
        </NavLink>
      </div>
    </div>
  );
}