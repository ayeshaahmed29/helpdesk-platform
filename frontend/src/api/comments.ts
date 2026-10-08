import { apiFetch } from "./client";

export interface Comment {
  id: number;
  ticket_id: number;
  author_id: number;
  body: string;
  is_internal: boolean;
  created_at: string;
}

export interface CommentCreate {
  body: string;
  is_internal: boolean;
}

export function listComments(ticketId: number): Promise<Comment[]> {
  return apiFetch<Comment[]>(`/tickets/${ticketId}/comments`);
}

export function createComment(ticketId: number, data: CommentCreate): Promise<Comment> {
  return apiFetch<Comment>(`/tickets/${ticketId}/comments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}