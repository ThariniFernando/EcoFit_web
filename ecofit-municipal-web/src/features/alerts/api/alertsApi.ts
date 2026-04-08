import { apiClient } from "../../../lib/apiClient";

export type RiskClass = "LOW" | "MEDIUM" | "HIGH" | "EMERGENCY";

export type CreateAlertPayload = {
  wardId: string;
  wardName?: string | null;
  riskClass: RiskClass;
  riskScore: number;
  tsPrediction?: string | null;
  lat?: number | null;
  lng?: number | null;
  title?: string | null;
  description?: string | null;
};

export type AlertItem = {
  _id: string;
  wardId: string;
  wardName?: string | null;
  riskClass: RiskClass;
  riskScore: number;
  tsPrediction?: string | null;
  lat?: number | null;
  lng?: number | null;
  title?: string | null;
  description?: string | null;
  status: "OPEN" | "CLOSED";
  createdAt: string;
};

export async function createAlert(
  payload: CreateAlertPayload
): Promise<AlertItem> {
  const res = await apiClient.post("/api/v1/alerts/create", payload);
  return res.data;
}

export async function fetchLatestAlerts(limit = 50): Promise<AlertItem[]> {
  const res = await apiClient.get("/api/v1/alerts/latest", {
    params: { limit },
  });
  return res.data;
}

export async function closeAlert(
  alertId: string
): Promise<{ ok: boolean; message: string }> {
  const res = await apiClient.post(`/api/v1/alerts/close/${alertId}`);
  return res.data;
}