import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export type SignUpPayload = {
  fullName: string;
  role: string;
  email: string;
  phone?: string;
  password: string;
  organization?: string;
};

export type SignInPayload = {
  email: string;
  password: string;
};

// ---------------------------------------------------------------------------
// Token helpers — used by apiClient to attach Authorization header
// ---------------------------------------------------------------------------
export function getToken(): string | null {
  return localStorage.getItem("token");
}

export function setToken(token: string): void {
  localStorage.setItem("token", token);
}

export function clearToken(): void {
  localStorage.removeItem("token");
}

// ---------------------------------------------------------------------------
// Auth calls
// ---------------------------------------------------------------------------
export async function signUp(payload: SignUpPayload) {
  const res = await axios.post(`${BASE_URL}/api/v1/auth/sign-up`, payload, {
    timeout: 10000,
  });
  // FIX: save token so subsequent requests are authenticated
  if (res.data?.token) {
    setToken(res.data.token);
  }
  return res.data;
}

export async function signIn(payload: SignInPayload) {
  const res = await axios.post(`${BASE_URL}/api/v1/auth/sign-in`, payload, {
    timeout: 10000,
  });
  // FIX: save token so subsequent requests are authenticated
  if (res.data?.token) {
    setToken(res.data.token);
  }
  return res.data;
}

export async function signOut() {
  clearToken();
}