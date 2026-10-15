const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const TOKEN_KEY = "token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  // The "detail" text from the backend, when it is a plain string.
  // Validation errors (422) send a list, so detail stays undefined for them.
  detail?: string;

  constructor(status: number, message: string, detail?: string) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

// AuthContext registers a callback here so a 401 anywhere in the app can
// reset the user state. The route guard then redirects to /login, so this
// file never needs to know about the router.
let onUnauthorized: (() => void) | null = null;

export function setUnauthorizedHandler(fn: (() => void) | null): void {
  onUnauthorized = fn;
}

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");

  const token = getToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (!response.ok) {
    // Session expired or token revoked: clear it and tell the app.
    // Only when a token was sent, so a wrong password on the login request
    // (also a 401) still shows its normal error instead of redirecting.
    if (response.status === 401 && token) {
      clearToken();
      onUnauthorized?.();
    }

    // Keep the backend's message, so pages can show it (for example the
    // different 403 reasons on PATCH /users/{id}).
    let detail: string | undefined;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // the error response had no JSON body
    }

    throw new ApiError(response.status, `Request failed: ${response.status}`, detail);
  }

  // Some endpoints (e.g. logout) may return an empty body.
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}