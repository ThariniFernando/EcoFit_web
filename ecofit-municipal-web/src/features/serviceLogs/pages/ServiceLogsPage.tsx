import React, { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import Modal from "../../../components/common/Modal";
import NewTripForm from "../components/NewTripForm";
import EditTripForm from "../components/EditTripForm";
import QuickNav from "../../../app/layout/QuickNav";
import {
  deleteServiceLog,
  getLiveServiceLogs,
  type ServiceLog,
} from "../api/serviceLogsApi";

type TimeWindowOption = { label: string; hours: number };

function formatDate(value: any) {
  try {
    const d = new Date(value);
    if (isNaN(d.getTime())) return String(value ?? "");
    return d.toLocaleString();
  } catch {
    return String(value ?? "");
  }
}

export default function ServiceLogsPage() {
  const options: TimeWindowOption[] = useMemo(
    () => [
      { label: "Last 24 hours", hours: 24 },
      { label: "Last 48 hours", hours: 48 },
      { label: "Last 7 days", hours: 168 },
    ],
    []
  );

  const [hours, setHours] = useState<number>(48);
  const [openNewTrip, setOpenNewTrip] = useState(false);
  const [openEditTrip, setOpenEditTrip] = useState(false);
  const [editingRow, setEditingRow] = useState<ServiceLog | null>(null);

  const {
    data: logs,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["serviceLogsLive", hours],
    queryFn: () => getLiveServiceLogs(hours),
  });

  const list = Array.isArray(logs) ? logs : [];

  const delMutation = useMutation({
    mutationFn: (id: string) => deleteServiceLog(id),
    onSuccess: () => refetch(),
  });

  return (
    <div className="ef-page">
      <QuickNav />

      <div className="ef-page-header">
        <div>
          <h1 className="ef-page-title">Service Logs</h1>
          <p className="ef-page-subtitle">View and manage daily service trips</p>
        </div>
      </div>

      <div className="ef-card ef-toolbar">
        <div className="ef-toolbar-left">
          <select
            className="ef-input"
            value={hours}
            onChange={(e) => setHours(Number(e.target.value))}
          >
            {options.map((o) => (
              <option key={o.hours} value={o.hours}>
                {o.label}
              </option>
            ))}
          </select>

          <button className="ef-btn ef-btn-secondary" onClick={() => refetch()} disabled={isFetching}>
            {isFetching ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        <button className="ef-btn ef-btn-primary" onClick={() => setOpenNewTrip(true)}>
          + New Trip
        </button>
      </div>

      <div className="ef-card">
        {isLoading ? (
          <div className="ef-empty-state">Loading service logs...</div>
        ) : isError ? (
          <div className="ef-alert ef-alert-error">
            <b>Failed to load service logs</b>
            <div style={{ marginTop: 8, whiteSpace: "pre-wrap", fontSize: 13 }}>
              {String((error as any)?.message ?? error)}
            </div>
          </div>
        ) : list.length === 0 ? (
          <div className="ef-empty-state">No logs found for selected time window.</div>
        ) : (
          <div className="ef-table-wrap">
            <table className="ef-table">
              <thead>
                <tr>
                  <th>Log ID</th>
                  <th>Ward</th>
                  <th>Type</th>
                  <th>Shift</th>
                  <th>Outcome</th>
                  <th>Volume</th>
                  <th>Start</th>
                  <th>End</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>

              <tbody>
                {list.map((row: any) => {
                  const wardLabel =
                    row?.ward?.wardName || row?.ward?.wardId || row?.wardId || "-";
                  const rowId = row?._id;

                  return (
                    <tr key={rowId || row?.logId}>
                      <td>{row?.logId ?? "-"}</td>
                      <td>{wardLabel}</td>
                      <td>{row?.serviceType ?? "-"}</td>
                      <td>{row?.shift ?? "-"}</td>
                      <td>{row?.outcome ?? "-"}</td>
                      <td>{row?.volumeLevel ?? "-"}</td>
                      <td>{formatDate(row?.startTime)}</td>
                      <td>{formatDate(row?.endTime)}</td>
                      <td className="text-right">
                        <div className="ef-actions-cell">
                          <button
                            className="ef-btn ef-btn-sm ef-btn-secondary"
                            onClick={() => {
                              setEditingRow(row);
                              setOpenEditTrip(true);
                            }}
                            disabled={!rowId}
                          >
                            Edit
                          </button>

                          <button
                            className="ef-btn ef-btn-sm ef-btn-danger"
                            onClick={() => {
                              if (!rowId) return;
                              if (confirm("Delete this service log?")) delMutation.mutate(rowId);
                            }}
                            disabled={!rowId || delMutation.isPending}
                          >
                            {delMutation.isPending ? "Deleting..." : "Delete"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Modal open={openNewTrip} title="New Service Trip" onClose={() => setOpenNewTrip(false)}>
        <NewTripForm
          onSuccess={() => {
            setOpenNewTrip(false);
            refetch();
          }}
        />
      </Modal>

      <Modal open={openEditTrip} title="Edit Service Trip" onClose={() => setOpenEditTrip(false)}>
        {editingRow ? (
          <EditTripForm
            row={editingRow}
            onSuccess={() => {
              setOpenEditTrip(false);
              setEditingRow(null);
              refetch();
            }}
          />
        ) : (
          <p>No trip selected.</p>
        )}
      </Modal>
    </div>
  );
}