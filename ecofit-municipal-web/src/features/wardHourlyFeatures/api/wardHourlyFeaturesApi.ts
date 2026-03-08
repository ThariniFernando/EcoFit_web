import { apiClient } from "../../../lib/apiClient";

export type WardHourlyFeature = {
  tsHour: string;
  wardId: string;

  precipMm: number;
  precipProb: number;
  tempC: number;
  rainMm: number;
  windKph: number;

  complaintsCount: number;
  avgSeverity: number;
  unresolvedComplaints: number;

  serviceCollected: number;
  servicePartial: number;
  serviceMissed: number;

  estimatedKg: number;
  binsCleared: number;
  overflowPoints: number;
};

export type WardHourlyFeaturesResponse = {
  wardId: string;
  hours: number;
  count: number;
  items: WardHourlyFeature[];
};

export async function fetchWardHourlyFeatures(
  wardId: string,
  hours: number
): Promise<WardHourlyFeaturesResponse> {
  const res = await apiClient.get("/api/v1/ward-hourly-features", {
    params: { wardId, hours },
  });
  return res.data;
}