import { apiClient } from "../../../lib/apiClient";

export type ComplaintStatus = "NEW" | "IN_PROGRESS" | "RESOLVED" | "REJECTED";

export type ComplaintWard = {
  wardId?: string;
  wardName?: string;
  wardNo?: number;
  center?: any;
};

export type ComplaintLocation = {
  address?: string;
  lat?: number;
  lng?: number;
  extra?: any;
};

export type Complaint = {
  id: string;
  complaintId?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
  source?: string | null;
  ward?: ComplaintWard | null;
  location?: ComplaintLocation | null;
  category?: string | null;
  severity?: number | null;
  description?: string | null;
  status: ComplaintStatus;
  statusHistory?: any[];
  assignedTo?: any;
  resolvedAt?: string | null;
  resolution?: string | null;
  wardId?: string;
  wardName?: string;
};

export type ComplaintListResponse = {
  items: Complaint[];
  total: number;
};

function normalizeStatus(value: any): ComplaintStatus {
  const s = String(value || "").trim().toUpperCase();

  if (s === "NEW" || s === "OPEN" || s === "PENDING") return "NEW";
  if (s === "IN_PROGRESS" || s === "INPROGRESS" || s === "IN-PROGRESS") return "IN_PROGRESS";
  if (s === "RESOLVED" || s === "DONE" || s === "CLOSED") return "RESOLVED";
  if (s === "REJECTED") return "REJECTED";

  return "NEW";
}

function toNumberOrUndefined(v: any): number | undefined {
  if (v === null || v === undefined || v === "") return undefined;
  const n = Number(v);
  return Number.isFinite(n) ? n : undefined;
}

function normalizeLocation(raw: any): ComplaintLocation | null {
  if (!raw || typeof raw !== "object") return null;

  let address = raw.address || raw.text || undefined;
  let lat = toNumberOrUndefined(raw.lat);
  let lng = toNumberOrUndefined(raw.lng);

  if ((lat === undefined || lng === undefined) && Array.isArray(raw.coordinates) && raw.coordinates.length >= 2) {
    lng = toNumberOrUndefined(raw.coordinates[0]);
    lat = toNumberOrUndefined(raw.coordinates[1]);
  }

  if (
    (lat === undefined || lng === undefined) &&
    raw.geojson &&
    typeof raw.geojson === "object" &&
    Array.isArray(raw.geojson.coordinates) &&
    raw.geojson.coordinates.length >= 2
  ) {
    lng = toNumberOrUndefined(raw.geojson.coordinates[0]);
    lat = toNumberOrUndefined(raw.geojson.coordinates[1]);
  }

  if (address === undefined && lat === undefined && lng === undefined) {
    return null;
  }

  return { address, lat, lng };
}

function normalizeComplaint(raw: any): Complaint {
  const rawWard = raw?.ward && typeof raw.ward === "object" ? raw.ward : null;

  return {
    id: String(raw?.id || raw?._id || ""),
    complaintId: raw?.complaintId ?? null,
    createdAt: raw?.createdAt ?? null,
    updatedAt: raw?.updatedAt ?? null,
    source: raw?.source ?? null,
    wardId: raw?.wardId || rawWard?.wardId || undefined,
    wardName: raw?.wardName || rawWard?.wardName || undefined,
    ward:
      rawWard || raw?.wardId || raw?.wardName
        ? {
            wardId: rawWard?.wardId || raw?.wardId || undefined,
            wardName: rawWard?.wardName || raw?.wardName || undefined,
            wardNo: rawWard?.wardNo || rawWard?.no || undefined,
            center: rawWard?.center || undefined,
          }
        : null,
    location: normalizeLocation(raw?.location),
    category: raw?.category ?? null,
    severity:
      typeof raw?.severity === "number"
        ? raw.severity
        : raw?.priority === "high"
        ? 3
        : raw?.priority === "medium"
        ? 2
        : raw?.priority === "low"
        ? 1
        : raw?.severity != null
        ? Number(raw.severity)
        : null,
    description: raw?.description ?? null,
    status: normalizeStatus(raw?.status),
    statusHistory: Array.isArray(raw?.statusHistory) ? raw.statusHistory : [],
    assignedTo: raw?.assignedTo,
    resolvedAt: raw?.resolvedAt ?? null,
    resolution: raw?.resolution ?? null,
  };
}

export async function listComplaints(params: {
  wardId?: string;
  status?: string;
  q?: string;
  hours?: number;
  limit?: number;
  skip?: number;
}): Promise<ComplaintListResponse> {
  const res = await apiClient.get("/api/v1/complaints", {
    params: {
      ...params,
      _t: Date.now(),
    },
  });

  const raw = res.data || {};
  const items = Array.isArray(raw.items) ? raw.items.map(normalizeComplaint) : [];
  const total = typeof raw.total === "number" ? raw.total : items.length;

  return { items, total };
}

export async function patchComplaintStatus(
  id: string,
  status: ComplaintStatus
): Promise<Complaint> {
  const res = await apiClient.patch(`/api/v1/complaints/${id}/status`, { status });
  return normalizeComplaint(res.data);
}