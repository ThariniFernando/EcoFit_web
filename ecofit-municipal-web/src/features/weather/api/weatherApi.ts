import { apiClient } from "../../../lib/apiClient";

export type WeatherHourlyItem = {
  tsHour: string;
  tempC: number;
  rainMm: number;
  windKph: number;
  precipMm: number;
  precipProb: number;
};

export type WeatherHourlyResponse = {
  hours: number;
  count: number;
  items: WeatherHourlyItem[];
};

export async function fetchWeatherHourly(
  hours: number = 48
): Promise<WeatherHourlyResponse> {
  const res = await apiClient.get("/api/v1/weather-hourly", {
    params: { hours },
  });
  return res.data;
}