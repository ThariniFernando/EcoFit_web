import { NavLink, useLocation } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { apiClient } from "../../lib/apiClient";

const links = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/risk-map", label: "Risk Map" },
  { to: "/action-plan", label: "Action Plan" },
  { to: "/service-logs", label: "Service Logs" },
  { to: "/complaints", label: "Complaints" },
  { to: "/knowledge-base", label: "Knowledge Base" },
];

const STORAGE_KEY = "complaints_last_seen_at";

function getOrInitLastSeen(): string {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (!saved) {
    const now = new Date().toISOString();
    localStorage.setItem(STORAGE_KEY, now);
    return now;
  }
  return saved;
}

export default function QuickNav() {
  const location = useLocation();
  const [unreadCount, setUnreadCount] = useState(0);
  const lastSeenRef = useRef<string>(getOrInitLastSeen());

  // When user visits /complaints — mark all as seen
  useEffect(() => {
    if (location.pathname === "/complaints") {
      const now = new Date().toISOString();
      localStorage.setItem(STORAGE_KEY, now);
      lastSeenRef.current = now;
      setUnreadCount(0);
    }
  }, [location.pathname]);

  // Poll for new complaints since last seen
  useEffect(() => {
    const load = async () => {
      try {
        if (location.pathname === "/complaints") {
          setUnreadCount(0);
          return;
        }

        const res = await apiClient.get("/api/v1/complaints", {
          params: { hours: 48, limit: 200 },
        });

        const items: any[] = res.data?.items || [];
        const since = new Date(lastSeenRef.current);

        const newOnes = items.filter((c) => {
          if (!c.createdAt) return false;
          return new Date(c.createdAt) > since;
        });

        setUnreadCount(newOnes.length);
      } catch {
        setUnreadCount(0);
      }
    };

    load();
    const interval = setInterval(load, 120000); // poll every 2 minutes
    return () => clearInterval(interval);
  }, [location.pathname]);

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
            style={{
              position: "relative",
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            {link.label}

            {link.to === "/complaints" && unreadCount > 0 && (
              <span
                style={{
                  background: "#e74c3c",
                  color: "#fff",
                  borderRadius: 10,
                  fontSize: 10,
                  fontWeight: 800,
                  minWidth: 18,
                  height: 18,
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  padding: "0 4px",
                  lineHeight: 1,
                }}
              >
                {unreadCount > 99 ? "99+" : unreadCount}
              </span>
            )}
          </NavLink>
        ))}
      </div>
    </div>
  );
}