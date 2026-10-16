import type { Role } from "./types";

export const ROLES: Role[] = ["customer", "agent", "admin", "owner"];

// The roles this role may give to other people.
// Only an owner can make an owner. The backend checks this again.
export function assignableRoles(role: Role): Role[] {
  return role === "owner" ? ROLES : ROLES.filter((r) => r !== "owner");
}

export function roleLabel(role: string): string {
  return role.charAt(0).toUpperCase() + role.slice(1);
}