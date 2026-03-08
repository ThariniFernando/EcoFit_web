import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { getWards } from "../../wards/api/wardsApi";
import { updateServiceLog, type ServiceLog } from "../api/serviceLogsApi";

type Ward = {
  wardId: string;
  wardName: string;
  wardNo?: number;
  center?: { lat?: number; lng?: number };
};

function toLocalInputFromISO(iso?: string) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(
    d.getHours()
  )}:${pad(d.getMinutes())}`;
}

export default function EditTripForm({
  row,
  onSuccess,
}: {
  row: ServiceLog;
  onSuccess: () => void;
}) {
  const id = row?._id;

  // Load wards list
  const { data: wards = [], isLoading: wardsLoading } = useQuery<Ward[]>({
    queryKey: ["wards"],
    queryFn: getWards,
  });

  // Initial values from row
  const initialWardId = row?.ward?.wardId || "";
  const initialWardName = row?.ward?.wardName || "";

  const [selectedWardId, setSelectedWardId] = useState(initialWardId);
  const [selectedWardName, setSelectedWardName] = useState(initialWardName);

  const [serviceType, setServiceType] = useState(row?.serviceType || "WASTE_COLLECTION");
  const [shift, setShift] = useState(row?.shift || "MORNING");
  const [outcome, setOutcome] = useState(row?.outcome || "COLLECTED");
  const [volumeLevel, setVolumeLevel] = useState(row?.volumeLevel || "MEDIUM");

  const [startTime, setStartTime] = useState(toLocalInputFromISO(row?.startTime));
  const [endTime, setEndTime] = useState(toLocalInputFromISO(row?.endTime));
  const [notes, setNotes] = useState(row?.notes || "");

  const mutation = useMutation({
    mutationFn: (payload: any) => updateServiceLog(id, payload),
    onSuccess: () => onSuccess(),
  });

  const wardMap = useMemo(() => {
    const m = new Map<string, Ward>();
    wards.forEach((w) => m.set(w.wardId, w));
    return m;
  }, [wards]);

  const handleWardChange = (wardId: string) => {
    const ward = wardMap.get(wardId);
    setSelectedWardId(ward?.wardId || "");
    setSelectedWardName(ward?.wardName || "");
  };

  const submit = () => {
    if (!id) return;

    const payload = {
      ward: { wardId: selectedWardId, wardName: selectedWardName },
      serviceType,
      shift,
      startTime: startTime ? new Date(startTime).toISOString() : undefined,
      endTime: endTime ? new Date(endTime).toISOString() : undefined,
      outcome,
      volumeLevel,
      notes,
    };

    mutation.mutate(payload);
  };

  return (
    <div className="space-y-4">
      <div
        className="grid"
        style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 12 }}
      >
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
        </div>

        <div>
          <label className="ef-label">Service Type</label>
          <select className="ef-input" value={serviceType} onChange={(e) => setServiceType(e.target.value)}>
            <option value="WASTE_COLLECTION">WASTE_COLLECTION</option>
            <option value="BIN_CLEARED">BIN_CLEARED</option>
            <option value="CLEANING">CLEANING</option>
            <option value="OTHER">OTHER</option>
          </select>
        </div>

        <div>
          <label className="ef-label">Shift</label>
          <select className="ef-input" value={shift} onChange={(e) => setShift(e.target.value)}>
            <option value="MORNING">MORNING</option>
            <option value="EVENING">EVENING</option>
            <option value="NIGHT">NIGHT</option>
          </select>
        </div>

        <div>
          <label className="ef-label">Outcome</label>
          <select className="ef-input" value={outcome} onChange={(e) => setOutcome(e.target.value)}>
            <option value="COLLECTED">COLLECTED</option>
            <option value="PARTIAL">PARTIAL</option>
            <option value="MISSED">MISSED</option>
          </select>
        </div>

        <div>
          <label className="ef-label">Volume Level</label>
          <select className="ef-input" value={volumeLevel} onChange={(e) => setVolumeLevel(e.target.value)}>
            <option value="LOW">LOW</option>
            <option value="MEDIUM">MEDIUM</option>
            <option value="HIGH">HIGH</option>
          </select>
        </div>

        <div>
          <label className="ef-label">Start Time</label>
          <input className="ef-input" type="datetime-local" value={startTime} onChange={(e) => setStartTime(e.target.value)} />
        </div>

        <div>
          <label className="ef-label">End Time</label>
          <input className="ef-input" type="datetime-local" value={endTime} onChange={(e) => setEndTime(e.target.value)} />
        </div>
      </div>

      <div>
        <label className="ef-label">Notes</label>
        <textarea className="ef-input" rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
      </div>

      <div className="flex items-center gap-2">
        <button className="ef-btn ef-btn-primary" onClick={submit} disabled={mutation.isPending}>
          {mutation.isPending ? "Saving..." : "Save Changes"}
        </button>
        {mutation.isError && <span className="text-red-600 text-sm">Update failed</span>}
      </div>
    </div>
  );
}