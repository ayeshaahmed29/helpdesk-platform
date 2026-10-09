import {
  useCallback, useEffect, useMemo, useState,
  type ReactNode,
} from "react";
import { loginRequest } from "../api/auth";
import {
  ApiError, TOKEN_KEY, apiFetch, clearToken, getToken, setUnauthorizedHandler,
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

  // Logs in with email and password. Throws ApiError if the login fails,
  // so the login page can show its own message.
  const login = useCallback(async (email: string, password: string) => {
    // Remove an old token first, so a wrong password (401) is not treated as an expired session
    clearToken();
    const { access_token } = await loginRequest(email, password);
    localStorage.setItem(TOKEN_KEY, access_token);
    try {
      setUser(await apiFetch<CurrentUser>("/auth/me"));
    } catch (err) {
      clearToken();
      setUser(null);
      throw err;
    }
  }, []);

  // Loads the current user again from the server (for example after a profile change)
  const refresh = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      return;
    }
    try {
      setUser(await apiFetch<CurrentUser>("/auth/me"));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) clearToken();
      setUser(null);
    }
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

  const value = useMemo(
    () => ({ user, loading, login, logout, refresh }),
    [user, loading, login, logout, refresh],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}