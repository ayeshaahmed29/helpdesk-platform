import type { Role } from "../auth/types";

export interface NavItem {
  label: string;
  path: string;
  roles: Role[];
  end?: boolean; // exact-match highlighting (use for parent paths like /settings)
}

export const NAV_ITEMS: NavItem[] = [
  { label: "Tickets", path: "/tickets", roles: ["agent", "admin", "owner"] },
  { label: "My tickets", path: "/portal", roles: ["customer"] },
  { label: "Team", path: "/settings/team", roles: ["admin", "owner"] },
  { label: "Settings", path: "/settings", roles: ["admin", "owner"], end: true },
  { label: "Audit log", path: "/audit-log", roles: ["admin", "owner"] },
];