// src/lib/apiClient.ts
import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL;

if (!baseURL) {
  // helps you catch env mistakes early
  console.warn("VITE_API_BASE_URL is missing. Check your .env file.");
}

export const apiClient = axios.create({
  baseURL: baseURL || "http://127.0.0.1:8000", // fallback
  timeout: 20000,
  headers: {
    "Content-Type": "application/json",
  },
});