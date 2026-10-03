import {
  useCallback, useEffect, useMemo, useState,
  type ReactNode,
} from "react";
import {
  ApiError, apiFetch, clearToken, getToken, setUnauthorizedHandler,
} from "../api/client";
import { AuthContext } from "./context";
import type { CurrentUser } from "./types";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  // Starts false when there is no token, so no effect needs to reset it.
  const [loading, setLoading] = useState<boolean>(() => !!getToken());

  // Any 401 anywhere in the app drops the user, and the guard redirects.
  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null));
    return () => setUnauthorizedHandler(null);
  }, []);

  useEffect(() => {
    if (!getToken()) return;

    apiFetch<CurrentUser>("/auth/me")
      .then(setUser)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) clearToken();
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiFetch("/auth/logout", { method: "POST" });
    } catch {
      // token may already be invalid, or Redis may be down (503); log out locally anyway
    }
    clearToken();
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, loading, logout }), [user, loading, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}