// src/features/wards/api/wardsApi.ts
import { apiClient } from "../../../lib/apiClient";

export type Ward = {
  wardId: string;
  wardName: string;
  wardNo?: number;
  center?: { lat?: number; lng?: number };
};

export async function getWards(): Promise<Ward[]> {
  const res = await apiClient.get("/api/v1/wards");
  return res.data;
}