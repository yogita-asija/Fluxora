import axios from "axios";

// Relative URLs work everywhere: Vite proxies /api in dev, Nginx routes it in Docker.
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api/v1",
  timeout: 10000,
});

// Health endpoints live outside the versioned API prefix.
export const health = axios.create({ baseURL: "/health", timeout: 5000 });

// The backend always returns { error: { code, message, details } }.
export function errorMessage(error) {
  return (
    error?.response?.data?.error?.message ||
    error?.message ||
    "Something went wrong"
  );
}
