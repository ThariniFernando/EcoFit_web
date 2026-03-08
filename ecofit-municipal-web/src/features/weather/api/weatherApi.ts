// src/features/weather/api/weatherApi.ts

const BASE_URL = "http://127.0.0.1:8000";

export type CurrentWeatherResponse = {
  location: string;
  tempC: number | null;
  humidity: number | null;
  windKph: number | null;
  condition: string | null;
  observedAt: string | null;
};

export async function fetchCurrentWeatherColombo(): Promise<CurrentWeatherResponse> {
  // IMPORTANT: this must match your backend weather route
  // If your backend route is different, change this URL.
  const url = `${BASE_URL}/api/v1/weather/current?city=${encodeURIComponent("Colombo")}`;

  const res = await fetch(url);
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || `HTTP ${res.status}`);
  }

  return await res.json();
}