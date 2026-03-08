import { apiClient } from "../../../lib/apiClient";

export type ServiceLog = {
  _id: string;
  logId?: string;
  createdAt?: string;
  updatedAt?: string;
  source?: string;

  ward?: { wardId?: string; wardName?: string } | any;

  serviceType: string;
  shift: string;
  startTime: string;
  endTime: string;
  outcome: string;
  volumeLevel: string;

  waste?: any;
  issues?: any[];
  notes?: string;

  createdBy?: any;
};

export type CreateServiceLogPayload = Omit<ServiceLog, "_id">;
export type UpdateServiceLogPayload = Partial<CreateServiceLogPayload>;

export async function getLiveServiceLogs(hours = 24) {
  const { data } = await apiClient.get<ServiceLog[]>("/api/v1/service-logs/live", {
    params: { hours },
  });
  return data;
}

export async function createServiceLog(payload: CreateServiceLogPayload) {
  const { data } = await apiClient.post<ServiceLog>("/api/v1/service-logs", payload);
  return data;
}

// ✅ add update
export async function updateServiceLog(id: string, payload: any) {
  const { data } = await apiClient.patch(`/api/v1/service-logs/${id}`, payload);
  return data;
}

// ✅ add delete
export async function deleteServiceLog(id: string) {
  const { data } = await apiClient.delete<{ ok: boolean }>(`/api/v1/service-logs/${id}`);
  return data;
}