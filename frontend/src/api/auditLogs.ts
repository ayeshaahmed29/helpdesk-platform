import { apiFetch } from "./client";

export type AuditLogItem = {
  id: number;
  action: string;
  actor_user_id: number | null;
  // null means the system did it
  actor_name: string | null;
  entity_type: string | null;
  entity_id: number | null;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type AuditLogPage = {
  items: AuditLogItem[];
  total: number;
  page: number;
  page_size: number;
};

export type AuditLogQuery = {
  action?: string;
  dateFrom?: string; // YYYY-MM-DD
  dateTo?: string; // YYYY-MM-DD
  page?: number;
  pageSize?: number;
};

export function listAuditLogs(query: AuditLogQuery = {}): Promise<AuditLogPage> {
  const params = new URLSearchParams();
  if (query.action) params.set("action", query.action);
  if (query.dateFrom) params.set("date_from", query.dateFrom);
  if (query.dateTo) params.set("date_to", query.dateTo);
  if (query.page) params.set("page", String(query.page));
  if (query.pageSize) params.set("page_size", String(query.pageSize));

  const qs = params.toString();
  return apiFetch<AuditLogPage>(`/audit-logs${qs ? `?${qs}` : ""}`);
}