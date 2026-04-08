import { apiClient } from "../../../lib/apiClient";

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
  probabilities?: number[] | null;
};

export type LatestPredictionsResponse = {
  tsPrediction: string;
  counts: Record<string, number>;
  items: PredictionMapItem[];
};

export async function fetchLatestPredictions(
  limit: number = 1000
): Promise<LatestPredictionsResponse> {
  const res = await apiClient.get("/api/v1/predictions/latest", {
    params: { limit },
  });
  return res.data;
}