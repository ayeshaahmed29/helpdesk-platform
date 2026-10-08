import { apiFetch } from "./client";

export type TicketStatus = "new" | "open" | "pending" | "resolved" | "closed";
export type TicketPriority = "low" | "normal" | "high" | "urgent";

export interface Ticket {
  id: number;
  subject: string;
  description: string;
  status: TicketStatus;
  priority: TicketPriority;
  organization_id: number;
  requester_id: number;
  assignee_id: number | null;
  first_response_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TicketPage {
  items: Ticket[];
  total: number;
  page: number;
  page_size: number;
}

export interface TicketFilters {
  status?: TicketStatus;
  priority?: TicketPriority;
  page?: number;
  pageSize?: number;
}

export function listTickets(filters: TicketFilters = {}): Promise<TicketPage> {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.priority) params.set("priority", filters.priority);
  params.set("page", String(filters.page ?? 1));
  params.set("page_size", String(filters.pageSize ?? 20));
  return apiFetch<TicketPage>(`/tickets?${params.toString()}`);
}
export interface TicketUpdate {
  status?: TicketStatus;
  priority?: TicketPriority;
  subject?: string;
  description?: string;
  assignee_id?: number | null;
}

export function getTicket(id: number): Promise<Ticket> {
  return apiFetch<Ticket>(`/tickets/${id}`);
}

export function updateTicket(id: number, data: TicketUpdate): Promise<Ticket> {
  return apiFetch<Ticket>(`/tickets/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}