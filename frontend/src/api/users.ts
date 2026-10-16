import type { Role } from "../auth/types";
import { apiFetch } from "./client";

export type TeamUser = {
  id: number;
  email: string;
  full_name: string | null;
  role: Role;
  is_active: boolean;
  organization_id: number;
  created_at: string;
};

export type UserUpdate = {
  role?: Role;
  is_active?: boolean;
};

export function listUsers(): Promise<TeamUser[]> {
  return apiFetch<TeamUser[]>("/users");
}

export function updateUser(id: number, data: UserUpdate): Promise<TeamUser> {
  return apiFetch<TeamUser>(`/users/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}