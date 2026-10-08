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

export function getInvite(token: string): Promise<InvitePreview> {
  return apiFetch<InvitePreview>(`/invites/${encodeURIComponent(token)}`);
}

export function acceptInvite(token: string, data: AcceptInviteData): Promise<AcceptedUser> {
  return apiFetch<AcceptedUser>(`/invites/${encodeURIComponent(token)}/accept`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}