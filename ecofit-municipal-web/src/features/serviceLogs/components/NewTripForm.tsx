import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { createServiceLog } from "../api/serviceLogsApi";
import { getWards } from "../../wards/api/wardsApi";

function toLocalInput(d: Date) {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(
    d.getHours()
  )}:${pad(d.getMinutes())}`;
}

type Ward = {
  wardId: string;
  wardName: string;
  wardNo?: number;
  center?: { lat?: number; lng?: number };
};

export default function NewTripForm({ onSuccess }: { onSuccess: () => void }) {
  const now = new Date();
  const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000);

  // Ward selection
  const [selectedWardId, setSelectedWardId] = useState("");
  const [selectedWardName, setSelectedWardName] = useState("");

  // Form fields
  const [serviceType, setServiceType] = useState("WASTE_COLLECTION");
  const [shift, setShift] = useState("MORNING");
  const [outcome, setOutcome] = useState("COLLECTED");
  const [volumeLevel, setVolumeLevel] = useState("MEDIUM");

  const [startTime, setStartTime] = useState(toLocalInput(oneHourAgo));
  const [endTime, setEndTime] = useState(toLocalInput(now));
  const [notes, setNotes] = useState("");

  // Load wards list
  const {
    data: wards = [],
    isLoading: wardsLoading,
    isError: wardsIsError,
  } = useQuery<Ward[]>({
    queryKey: ["wards"],
    queryFn: getWards,
  });

  const mutation = useMutation({
    mutationFn: createServiceLog,
    onSuccess: () => onSuccess(),
  });

  const handleWardChange = (wardId: string) => {
    const ward = wards.find((w) => w.wardId === wardId);
    setSelectedWardId(ward?.wardId || "");
    setSelectedWardName(ward?.wardName || "");
  };

  const submit = () => {
    // basic guard
    if (!selectedWardId) return;

    const payload = {
      logId: `SRV-WEB-${Date.now()}`,
      source: "municipal_web",
      ward: {
        wardId: selectedWardId,
        wardName: selectedWardName,
      },
      serviceType,
      shift,
      startTime: new Date(startTime).toISOString(),
      endTime: new Date(endTime).toISOString(),
      outcome,
      volumeLevel,
      waste: {},
      issues: [],
      notes: notes || "",
      createdBy: {
        role: "municipal_user",
        name: "Municipal Web",
      },
    };

    mutation.mutate(payload as any);
  };

  return (
    <div className="space-y-4">
      {/* Wards loading/error helper */}
      {wardsLoading && (
        <div className="text-sm" style={{ color: "#666" }}>
          Loading wards...
        </div>
      )}
      {wardsIsError && (
        <div className="text-sm" style={{ color: "red" }}>
          Failed to load wards. Check API `/api/v1/wards` and VITE_API_BASE_URL.
        </div>
      )}

      <div
        className="grid"
        style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 12 }}
      >
        {/* Ward dropdown */}
        <div>
          <label className="ef-label">Ward</label>
          <select
            className="ef-input"
            value={selectedWardId}
            onChange={(e) => handleWardChange(e.target.value)}
            disabled={wardsLoading}
          >
            <option value="">-- Select Ward --</option>
            {wards.map((w) => (
              <option key={w.wardId} value={w.wardId}>
                {w.wardName} ({w.wardId})
              </option>
            ))}
          </select>
          {selectedWardId && (
            <div className="text-xs mt-1" style={{ color: "#666" }}>
              Selected: <b>{selectedWardName}</b> / {selectedWardId}
            </div>
          )}
        </div>

        <div>
          <label className="ef-label">Service Type</label>
          <select
            className="ef-input"
            value={serviceType}
            onChange={(e) => setServiceType(e.target.value)}
          >
            <option value="WASTE_COLLECTION">WASTE_COLLECTION</option>
            <option value="BIN_CLEARED">BIN_CLEARED</option>
            <option value="CLEANING">CLEANING</option>
            <option value="OTHER">OTHER</option>
          </select>
        </div>

        <div>
          <label className="ef-label">Shift</label>
          <select
            className="ef-input"
            value={shift}
            onChange={(e) => setShift(e.target.value)}
          >
            <option value="MORNING">MORNING</option>
            <option value="EVENING">EVENING</option>
            <option value="NIGHT">NIGHT</option>
          </select>
        </div>

        <div>
          <label className="ef-label">Outcome</label>
          <select
            className="ef-input"
            value={outcome}
            onChange={(e) => setOutcome(e.target.value)}
          >
            <option value="COLLECTED">COLLECTED</option>
            <option value="PARTIAL">PARTIAL</option>
            <option value="MISSED">MISSED</option>
          </select>
        </div>

        <div>
          <label className="ef-label">Volume Level</label>
          <select
            className="ef-input"
            value={volumeLevel}
            onChange={(e) => setVolumeLevel(e.target.value)}
          >
            <option value="LOW">LOW</option>
            <option value="MEDIUM">MEDIUM</option>
            <option value="HIGH">HIGH</option>
          </select>
        </div>

        <div>
          <label className="ef-label">Start Time</label>
          <input
            className="ef-input"
            type="datetime-local"
            value={startTime}
            onChange={(e) => setStartTime(e.target.value)}
          />
        </div>

        <div>
          <label className="ef-label">End Time</label>
          <input
            className="ef-input"
            type="datetime-local"
            value={endTime}
            onChange={(e) => setEndTime(e.target.value)}
          />
        </div>
      </div>

      <div>
        <label className="ef-label">Notes</label>
        <textarea
          className="ef-input"
          rows={3}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Notes..."
        />
      </div>

      <div className="flex items-center gap-2">
        <button
          className="ef-btn ef-btn-primary"
          onClick={submit}
          disabled={mutation.isPending || !selectedWardId}
        >
          {mutation.isPending ? "Saving..." : "Save Trip"}
        </button>

        {mutation.isError && (
          <span className="text-red-600 text-sm">Save failed</span>
        )}
      </div>
    </div>
  );
}