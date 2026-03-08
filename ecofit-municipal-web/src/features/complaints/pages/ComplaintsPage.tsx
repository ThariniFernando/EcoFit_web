import { useEffect, useMemo, useState } from "react";
import {
  listComplaints,
  patchComplaintStatus,
  type Complaint,
  type ComplaintStatus,
} from "../api/complaintsApi";
import { getWards, type Ward } from "../../wards/api/wardsApi";
import QuickNav from "../../../app/layout/QuickNav";

const STATUSES: ComplaintStatus[] = ["NEW", "IN_PROGRESS", "RESOLVED", "REJECTED"];

const TIME_OPTIONS = [
  { label: "Last 6 hours", value: 6 },
  { label: "Last 24 hours", value: 24 },
  { label: "Last 48 hours", value: 48 },
];

const STATUS_TABS: Array<{ label: string; value: string }> = [
  { label: "All", value: "" },
  { label: "New", value: "NEW" },
  { label: "In Progress", value: "IN_PROGRESS" },
  { label: "Resolved", value: "RESOLVED" },
  { label: "Rejected", value: "REJECTED" },
];

function formatDate(s?: string | null) {
  if (!s) return "-";
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return s;
  return d.toLocaleString();
}

function wardLabel(c: Complaint) {
  const w = c.ward;
  if (!w) return "-";
  return w.wardName || w.wardId || "-";
}

function locationLabel(c: Complaint) {
  const loc = c.location;
  if (!loc) return "-";
  if (loc.address) return loc.address;

  const parts: string[] = [];
  if (typeof loc.lat === "number") parts.push(`lat:${loc.lat}`);
  if (typeof loc.lng === "number") parts.push(`lng:${loc.lng}`);
  return parts.length ? parts.join(", ") : "-";
}

export default function ComplaintsPage() {
  const [wards, setWards] = useState<Ward[]>([]);
  const [items, setItems] = useState<Complaint[]>([]);
  const [total, setTotal] = useState(0);

  const [wardId, setWardId] = useState("");
  const [status, setStatus] = useState("");
  const [hours, setHours] = useState<number>(48);
  const [q, setQ] = useState("");

  const [limit] = useState(50);
  const [skip, setSkip] = useState(0);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");

  const params = useMemo(
    () => ({
      wardId: wardId || undefined,
      status: status || undefined,
      q: q || undefined,
      hours: hours || undefined,
      limit,
      skip,
    }),
    [wardId, status, q, hours, limit, skip]
  );

  const canPrev = skip > 0;
  const canNext = skip + limit < total;

  const summary = useMemo(() => {
    return {
      NEW: items.filter((x) => x.status === "NEW").length,
      IN_PROGRESS: items.filter((x) => x.status === "IN_PROGRESS").length,
      RESOLVED: items.filter((x) => x.status === "RESOLVED").length,
      REJECTED: items.filter((x) => x.status === "REJECTED").length,
    };
  }, [items]);

  async function loadWardsAndComplaints() {
    setLoading(true);
    setError("");

    try {
      const w = await getWards();
      setWards(w);

      const res = await listComplaints(params);
      setItems(res.items);
      setTotal(res.total);
    } catch (e: any) {
      setError(e?.message || "Failed to load complaints");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadWardsAndComplaints();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wardId, status, hours, skip]);

  async function onApply() {
    setSkip(0);
    await loadWardsAndComplaints();
  }

  async function onRefresh() {
    await loadWardsAndComplaints();
  }

  async function onUpdateStatus(id: string, next: ComplaintStatus) {
    try {
      setError("");
      const updated = await patchComplaintStatus(id, next);
      setItems((prev) => prev.map((c) => (c.id === id ? updated : c)));
    } catch (e: any) {
      setError(e?.message || "Failed to update status");
    }
  }

  return (
    <div className="ef-page">
      <QuickNav />

      <div className="ef-page-header">
        <div>
          <h1 className="ef-page-title">Complaints</h1>
          <p className="ef-page-subtitle">
            Monitor recent complaints, filter by urgency window, and update status
          </p>
        </div>
      </div>

      <div className="ef-card ef-content-stack">
        <div className="ef-section-head">
          <h3>Complaints Control Panel</h3>
        </div>

        <div className="ef-segment-group">
          {STATUS_TABS.map((tab) => {
            const active = status === tab.value;
            return (
              <button
                key={tab.label}
                className={active ? "ef-btn ef-btn-primary" : "ef-btn ef-btn-secondary"}
                onClick={() => {
                  setStatus(tab.value);
                  setSkip(0);
                }}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        <div className="ef-summary-grid">
          <div className="ef-stat-card">
            <div className="ef-stat-title">New</div>
            <div className="ef-stat-value">{summary.NEW}</div>
          </div>
          <div className="ef-stat-card">
            <div className="ef-stat-title">In Progress</div>
            <div className="ef-stat-value">{summary.IN_PROGRESS}</div>
          </div>
          <div className="ef-stat-card">
            <div className="ef-stat-title">Resolved</div>
            <div className="ef-stat-value">{summary.RESOLVED}</div>
          </div>
          <div className="ef-stat-card">
            <div className="ef-stat-title">Rejected</div>
            <div className="ef-stat-value">{summary.REJECTED}</div>
          </div>
        </div>

        <div className="ef-toolbar-grid">
          <div className="ef-field">
            <label className="ef-label">Time Window</label>
            <select
              className="ef-input"
              value={hours}
              onChange={(e) => {
                setHours(Number(e.target.value));
                setSkip(0);
              }}
            >
              {TIME_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div className="ef-field">
            <label className="ef-label">Ward</label>
            <select
              className="ef-input"
              value={wardId}
              onChange={(e) => {
                setWardId(e.target.value);
                setSkip(0);
              }}
            >
              <option value="">All wards</option>
              {wards.map((w) => (
                <option key={w.wardId} value={w.wardId}>
                  {w.wardName}
                </option>
              ))}
            </select>
          </div>

          <div className="ef-field ef-field-wide">
            <label className="ef-label">Search</label>
            <div className="ef-toolbar-actions">
              <input
                className="ef-input"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="category / description / complaint id..."
              />
              <button className="ef-btn ef-btn-primary" onClick={onApply}>
                Apply
              </button>
              <button className="ef-btn ef-btn-secondary" onClick={onRefresh}>
                Refresh
              </button>
            </div>
          </div>
        </div>

        {error ? (
          <div className="ef-alert ef-alert-error">
            <b>Error:</b> {error}
          </div>
        ) : null}

        <div className="ef-toolbar-meta">
          <div>
            {loading
              ? "Loading complaints..."
              : `Showing ${items.length} of ${total} complaints`}
          </div>
          <div>
            Window: <b>{hours}h</b>
            {status ? <> | Status: <b>{status}</b></> : null}
            {wardId ? <> | Ward: <b>{wardId}</b></> : null}
          </div>
        </div>

        <div className="ef-table-wrap">
          <table className="ef-table">
            <thead>
              <tr>
                <th>Created</th>
                <th>Complaint ID</th>
                <th>Ward</th>
                <th>Category</th>
                <th>Severity</th>
                <th>Description</th>
                <th>Location</th>
                <th>Status</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>

            <tbody>
              {!loading && items.length === 0 ? (
                <tr>
                  <td colSpan={9} className="ef-empty-cell">
                    No complaints found for the selected filters.
                  </td>
                </tr>
              ) : (
                items.map((c) => (
                  <tr key={c.id}>
                    <td>{formatDate(c.createdAt)}</td>
                    <td>{c.complaintId || "-"}</td>
                    <td>{wardLabel(c)}</td>
                    <td>{c.category || "-"}</td>
                    <td>{typeof c.severity === "number" ? c.severity : "-"}</td>
                    <td>{c.description || "-"}</td>
                    <td>{locationLabel(c)}</td>
                    <td>{c.status}</td>
                    <td className="text-right">
                      <div className="ef-actions-cell">
                        {STATUSES.filter((s) => s !== c.status).map((s) => (
                          <button
                            key={s}
                            className="ef-btn ef-btn-sm ef-btn-secondary"
                            onClick={() => onUpdateStatus(c.id, s)}
                          >
                            Mark {s}
                          </button>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="ef-toolbar-meta">
          <div>
            Page: {Math.floor(skip / limit) + 1} (limit {limit})
          </div>

          <div className="ef-toolbar-actions">
            <button
              className="ef-btn ef-btn-secondary"
              disabled={!canPrev}
              onClick={() => setSkip((s) => Math.max(0, s - limit))}
            >
              Prev
            </button>
            <button
              className="ef-btn ef-btn-secondary"
              disabled={!canNext}
              onClick={() => setSkip((s) => s + limit)}
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}