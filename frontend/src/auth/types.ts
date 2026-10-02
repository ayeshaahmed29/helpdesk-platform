export type Role = "customer" | "agent" | "admin" | "owner";

export interface CurrentUser {
  id: number;
  email: string;
  full_name?: string;
  role: Role;
}