import { NavLink } from "react-router-dom";

const links = [
  { to: "/risk-map", label: "Risk Map" },
  { to: "/action-plan", label: "Action Plan" },
  { to: "/service-logs", label: "Service Logs" },
  { to: "/complaints", label: "Complaints" },
  { to: "/knowledge-base", label: "Knowledge Base" },
];

export default function QuickNav() {
  return (
    <div className="ef-topnav">
      <div className="ef-brand">
        <div className="ef-brand-icon">♻️</div>

        <div className="ef-brand-text">
          <h1 className="ef-brand-title">EcoFit Municipal</h1>
          <p className="ef-brand-subtitle">Operations Dashboard</p>
        </div>
      </div>

      <div className="ef-nav-links">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            className={({ isActive }) =>
              `ef-nav-link ${isActive ? "active" : ""}`
            }
          >
            {link.label}
          </NavLink>
        ))}
      </div>
    </div>
  );
}