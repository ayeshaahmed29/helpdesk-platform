import { apiFetch } from "./client";

export type TicketsPerDayItem = {
  day: string; // YYYY-MM-DD
  count: number;
};

export type TicketsPerDayResponse = {
  items: TicketsPerDayItem[];
};

export type AvgFirstResponseResponse = {
  average_hours: number | null;
  ticket_count: number;
};

export type ReportsQuery = {
  dateFrom?: string; // YYYY-MM-DD
  dateTo?: string; // YYYY-MM-DD
};

function buildQuery(query: ReportsQuery): string {
  const params = new URLSearchParams();
  if (query.dateFrom) params.set("date_from", query.dateFrom);
  if (query.dateTo) params.set("date_to", query.dateTo);
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function getTicketsPerDay(query: ReportsQuery = {}): Promise<TicketsPerDayResponse> {
  return apiFetch<TicketsPerDayResponse>(`/reports/tickets-per-day${buildQuery(query)}`);
}

export function getAvgFirstResponse(query: ReportsQuery = {}): Promise<AvgFirstResponseResponse> {
  return apiFetch<AvgFirstResponseResponse>(`/reports/avg-first-response${buildQuery(query)}`);
}