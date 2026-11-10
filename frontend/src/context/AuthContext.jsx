import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, clearToken, getToken, onUnauthorized, setToken } from "../api/client.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  // If a token survived a reload we must ask the API who it belongs to before rendering.
  const [loading, setLoading] = useState(() => Boolean(getToken()));

  useEffect(() => {
    onUnauthorized(() => setUser(null));
  }, []);

  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      return undefined;
    }
    let cancelled = false;
    api
      .get("/auth/me")
      .then((response) => {
        if (!cancelled) setUser(response.data);
      })
      .catch(() => {
        if (!cancelled) {
          clearToken();
          setUser(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    setToken(data.access_token);
    try {
      const me = await api.get("/auth/me");
      setUser(me.data);
    } catch (error) {
      clearToken();
      throw error;
    }
  }, []);

  const register = useCallback(
    async ({ email, fullName, password }) => {
      await api.post("/auth/register", { email, full_name: fullName, password });
      await login(email, password);
    },
    [login],
  );

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, register, logout }),
    [user, loading, login, register, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}
