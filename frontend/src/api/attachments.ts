import { apiFetch } from "./client";

export interface Attachment {
  id: number;
  ticket_id: number;
  comment_id: number | null;
  uploader_id: number;
  filename: string;
  content_type: string;
  size: number;
  created_at: string;
}

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export function listAttachments(ticketId: number): Promise<Attachment[]> {
  return apiFetch<Attachment[]>(`/tickets/${ticketId}/attachments`);
}

export async function uploadAttachment(ticketId: number, file: File): Promise<Attachment> {
  const token = localStorage.getItem("token");
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/tickets/${ticketId}/attachments`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.detail ?? res.statusText);
  }
  return res.json();
}

export async function downloadAttachment(attachmentId: number, filename: string): Promise<void> {
  const token = localStorage.getItem("token");
  const res = await fetch(`${API_BASE}/attachments/${attachmentId}/download`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error("Download failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}