import axios from "axios";

// The access token lives in sessionStorage: it is dropped when the tab closes and is never
// sent anywhere except the API. (The CSP set by Nginx limits what injected script could do.)
const TOKEN_KEY = "orderflow-token";

export function getToken() {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token) {
  try {
    sessionStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* storage unavailable: the session just won't survive a reload */
  }
}

export function clearToken() {
  try {
    sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* nothing to clear */
  }
}

// AuthContext registers a callback so an expired or revoked token logs the user out.
let unauthorizedHandler = null;
export function onUnauthorized(handler) {
  unauthorizedHandler = handler;
}

// Relative URLs work everywhere: Vite proxies /api in dev, Nginx routes it in Docker.
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api/v1",
  timeout: 10000,
});

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const url = error.config?.url ?? "";
    const isCredentialCall = url.startsWith("/auth/login") || url.startsWith("/auth/register");
    // A 401 anywhere else means the session is over (expired, or the account was disabled).
    if (error.response?.status === 401 && !isCredentialCall && getToken()) {
      clearToken();
      if (unauthorizedHandler) unauthorizedHandler();
    }
    return Promise.reject(error);
  },
);

// Health endpoints live outside the versioned API prefix.
export const health = axios.create({ baseURL: "/health", timeout: 5000 });

// The backend always returns { error: { code, message, details } }.
export function errorMessage(error) {
  const apiError = error?.response?.data?.error;
  if (apiError?.code === "validation_error" && Array.isArray(apiError.details)) {
    return apiError.details
      .map((d) => {
        const field = d.loc.filter((part) => part !== "body").join(".");
        return field ? `${field}: ${d.message}` : d.message;
      })
      .join("; ");
  }
  if (apiError?.message) return apiError.message;
  if (error?.code === "ERR_NETWORK") return "Cannot reach the server. Check your connection.";
  return error?.message || "Something went wrong";
}

// One key per order attempt: retrying the same attempt can never create a second order.
export function newIdempotencyKey() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}
