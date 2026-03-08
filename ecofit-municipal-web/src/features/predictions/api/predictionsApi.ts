// src/features/predictions/api/predictionsApi.ts

const BASE_URL = "http://127.0.0.1:8000";

export type RiskClass = "LOW" | "MEDIUM" | "HIGH" | "EMERGENCY";

export type PredictionMapItem = {
  _id: string;

  wardId: string;
  wardName?: string | null;

  lat: number | null;
  lng: number | null;

  riskClass: RiskClass;
  riskScore: number;

  tsPrediction?: string | null;

  // optional
  probabilities?: number[] | null;
};

export type LatestPredictionsResponse = {
  tsPrediction: string;
  counts: Record<string, number>;
  items: PredictionMapItem[];
};

// ✅ IMPORTANT: This takes a NUMBER, not an object
export async function fetchLatestPredictions(limit: number = 1000): Promise<LatestPredictionsResponse> {
  const url = `${BASE_URL}/api/v1/predictions/latest?limit=${encodeURIComponent(limit)}`;

  const res = await fetch(url);
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || `HTTP ${res.status}`);
  }

  return await res.json();
}