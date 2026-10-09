import { apiFetch } from "./client";

export interface Tag {
  id: number;
  name: string;
  color: string | null;
  organization_id: number;
  created_at: string;
}

export interface TagCreate {
  name: string;
  color?: string | null;
}

export function listTags(): Promise<Tag[]> {
  return apiFetch<Tag[]>("/tags");
}

export function createTag(data: TagCreate): Promise<Tag> {
  return apiFetch<Tag>("/tags", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export function deleteTag(tagId: number): Promise<void> {
  return apiFetch<void>(`/tags/${tagId}`, {
    method: "DELETE",
  });
}

export function addTagToTicket(tagId: number, ticketId: number): Promise<void> {
  return apiFetch<void>(`/tags/${tagId}/tickets/${ticketId}`, {
    method: "POST",
  });
}

export function removeTagFromTicket(tagId: number, ticketId: number): Promise<void> {
  return apiFetch<void>(`/tags/${tagId}/tickets/${ticketId}`, {
    method: "DELETE",
  });
}