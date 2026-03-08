import { useEffect, useState } from "react";
import {
  fetchWardHourlyFeatures,
  type WardHourlyFeature,
} from "../api/wardHourlyFeaturesApi";
import { getWards, type Ward } from "../../wards/api/wardsApi";

type WardOption = { id: string; name: string };

export default function WardHourlyFeaturesPage() {
  const [wardOptions, setWardOptions] = useState<WardOption[]>([]);
  const [selectedWardId, setSelectedWardId] = useState<string>("");
  const [hours, setHours] = useState<number>(48);
  const [data, setData] = useState<WardHourlyFeature[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ✅ Load wards once
  useEffect(() => {
    (async () => {
      try {
        const wards: Ward[] = await getWards();
        const mapped: WardOption[] = wards.map((w) => ({
          id: w.wardId,
          name: w.wardName,
        }));
        setWardOptions(mapped);
      } catch (e) {
        setWardOptions([]);
      }
    })();
  }, []);

  async function load() {
    if (!selectedWardId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchWardHourlyFeatures(selectedWardId, hours);
      setData(res.items || []);
    } catch (e: any) {
      setError(e?.message || "Failed to load ward hourly features");
      setData([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedWardId, hours]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[rgb(var(--primary))]">
          Ward Hourly Features
        </h1>
        <p className="ef-subtitle mt-1">
          View hourly features per ward (model input preview)
        </p>
      </div>

      <div className="ef-card p-4 space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <div className="text-sm text-[rgb(var(--muted))]">Ward</div>
            <select
              className="w-full"
              value={selectedWardId}
              onChange={(e) => setSelectedWardId(e.target.value)}
            >
              <option value="">Select ward</option>
              {wardOptions.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>
            <div className="text-xs text-[rgb(var(--muted))] mt-1">
              Selected wardId: <b>{selectedWardId || "-"}</b>
            </div>
          </div>

          <div>
            <div className="text-sm text-[rgb(var(--muted))]">Hours</div>
            <select
              className="w-full"
              value={hours}
              onChange={(e) => setHours(Number(e.target.value))}
            >
              <option value={24}>Last 24 hours</option>
              <option value={48}>Last 48 hours</option>
              <option value={168}>Last 7 days</option>
            </select>
          </div>

          <div className="flex items-end gap-2">
            <button
              className="ef-btn"
              onClick={load}
              disabled={!selectedWardId || loading}
            >
              {loading ? "Loading..." : "Refresh"}
            </button>
            {error && <div className="text-sm text-red-600">{error}</div>}
          </div>
        </div>
      </div>

      <div className="ef-card p-4 overflow-auto">
        <div className="text-sm mb-2">
          Showing <b>{data.length}</b> rows
        </div>

        <table className="min-w-full border">
          <thead>
            <tr>
              <th className="border px-2 py-1">Time</th>
              <th className="border px-2 py-1">Complaints</th>
              <th className="border px-2 py-1">Unresolved</th>
              <th className="border px-2 py-1">Collected</th>
              <th className="border px-2 py-1">Missed</th>
              <th className="border px-2 py-1">Estimated Kg</th>
              <th className="border px-2 py-1">Overflow</th>
              <th className="border px-2 py-1">Temp</th>
              <th className="border px-2 py-1">Rain</th>
              <th className="border px-2 py-1">Wind</th>
            </tr>
          </thead>

          <tbody>
            {data.map((row, idx) => (
              <tr key={idx}>
                <td className="border px-2 py-1">
                  {row.tsHour ? new Date(row.tsHour).toLocaleString() : ""}
                </td>
                <td className="border px-2 py-1">{row.complaintsCount ?? 0}</td>
                <td className="border px-2 py-1">
                  {row.unresolvedComplaints ?? 0}
                </td>
                <td className="border px-2 py-1">{row.serviceCollected ?? 0}</td>
                <td className="border px-2 py-1">{row.serviceMissed ?? 0}</td>
                <td className="border px-2 py-1">{row.estimatedKg ?? 0}</td>
                <td className="border px-2 py-1">{row.overflowPoints ?? 0}</td>
                <td className="border px-2 py-1">{row.tempC ?? 0}</td>
                <td className="border px-2 py-1">{row.rainMm ?? 0}</td>
                <td className="border px-2 py-1">{row.windKph ?? 0}</td>
              </tr>
            ))}

            {data.length === 0 && !loading && (
              <tr>
                <td className="border px-2 py-2 text-center" colSpan={10}>
                  No data
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}