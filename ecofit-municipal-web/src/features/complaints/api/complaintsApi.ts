// src/features/complaints/api/complaintsApi.ts
import { apiClient } from "../../../lib/apiClient";

export type ComplaintStatus = "NEW" | "IN_PROGRESS" | "RESOLVED" | "REJECTED";

export type ComplaintWard = {
  wardId?: string;
  wardName?: string;
  wardNo?: number;
};

export type ComplaintLocation = {
  address?: string;
  lat?: number;
  lng?: number;
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
};

export type ComplaintListResponse = {
  items: Complaint[];
  total: number;
};

export async function listComplaints(params: {
  wardId?: string;
  status?: string;
  q?: string;
  hours?: number;
  limit?: number;
  skip?: number;
}): Promise<ComplaintListResponse> {
  const res = await apiClient.get("/api/v1/complaints", { params });
  return res.data;
}

export async function patchComplaintStatus(
  id: string,
  status: ComplaintStatus
): Promise<Complaint> {
  const res = await apiClient.patch(`/api/v1/complaints/${id}/status`, { status });
  return res.data;
}