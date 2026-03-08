import axios from "axios";

const BASE_URL = "http://127.0.0.1:8000";

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

export async function signUp(payload: SignUpPayload) {
  const res = await axios.post(`${BASE_URL}/api/v1/auth/sign-up`, payload, {
    timeout: 10000,
  });
  return res.data;
}

export async function signIn(payload: SignInPayload) {
  const res = await axios.post(`${BASE_URL}/api/v1/auth/sign-in`, payload, {
    timeout: 10000,
  });
  return res.data;
}