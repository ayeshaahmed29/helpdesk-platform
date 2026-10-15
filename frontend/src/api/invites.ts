import type { Role } from "../auth/types";
import { apiFetch } from "./client";

export type InvitePreview = {
  email: string;
  role: string;
  organization_name: string;
  expires_at: string;
};

export type AcceptInviteData = {
  full_name: string;
  password: string;
};

export type AcceptedUser = {
  id: number;
  email: string;
  full_name: string | null;
  role: string;
  organization_id: number;
};

export type InviteItem = {
  id: number;
  email: string;
  role: string;
  status: "pending" | "accepted" | "expired";
  invited_by: number | null;
  expires_at: string;
  accepted_at: string | null;
  created_at: string;
};

export type CreateInviteData = {
  email: string;
  role: Role;
};

export function getInvite(token: string): Promise<InvitePreview> {
  return apiFetch<InvitePreview>(`/invites/${encodeURIComponent(token)}`);
}

export function acceptInvite(token: string, data: AcceptInviteData): Promise<AcceptedUser> {
  return apiFetch<AcceptedUser>(`/invites/${encodeURIComponent(token)}/accept`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function createInvite(data: CreateInviteData): Promise<InviteItem> {
  return apiFetch<InviteItem>("/invites", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function listInvites(): Promise<InviteItem[]> {
  return apiFetch<InviteItem[]>("/invites");
}