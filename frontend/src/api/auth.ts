import { apiFetch } from "./client";

export type UserRole = "customer" | "agent" | "admin" | "owner";

export interface CurrentUser {
  id: number;
  email: string;
  full_name: string;
  role: UserRole;
  organization_id: number;
}

export function getCurrentUser(): Promise<CurrentUser> {
  return apiFetch<CurrentUser>("/auth/me");
}