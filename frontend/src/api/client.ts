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

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
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
    // Session expired or token revoked: clear it and send the user to login.
    // Only when a token was sent, so a wrong password on the login request
    // (also a 401) still shows its normal error instead of redirecting.
    if (response.status === 401 && token) {
      clearToken();
      if (window.location.pathname !== "/login") {
        window.location.assign("/login");
      }
    }
    throw new ApiError(response.status, `Request failed: ${response.status}`);
  }

  // Some endpoints (e.g. logout) may return an empty body.
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}