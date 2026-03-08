// src/features/alerts/api/alertsApi.ts

const BASE_URL = "http://127.0.0.1:8000";

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

// ✅ MUST be named exactly createAlert
export async function createAlert(payload: CreateAlertPayload): Promise<AlertItem> {
  const res = await fetch(`${BASE_URL}/api/v1/alerts/create`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || `HTTP ${res.status}`);
  }

  return await res.json();
}

export async function fetchLatestAlerts(limit = 50): Promise<AlertItem[]> {
  const res = await fetch(`${BASE_URL}/api/v1/alerts/latest?limit=${limit}`);
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || `HTTP ${res.status}`);
  }
  return await res.json();
}

export async function closeAlert(alertId: string): Promise<{ ok: boolean; message: string }> {
  const res = await fetch(`${BASE_URL}/api/v1/alerts/close/${alertId}`, {
    method: "POST",
  });

  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || `HTTP ${res.status}`);
  }
  return await res.json();
}