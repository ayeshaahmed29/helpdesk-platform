import { useEffect, useState } from "react";

import {
  getAvgFirstResponse,
  getTicketsPerDay,
  type AvgFirstResponseResponse,
  type TicketsPerDayResponse,
} from "../api/reports";
import { ApiError } from "../api/client";

type Result = {
  key: string;
  ticketsPerDay?: TicketsPerDayResponse;
  avgFirstResponse?: AvgFirstResponseResponse;
  error?: string;
};

function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 400) return "The start date must not be after the end date.";
    if (err.status === 403) return "You do not have permission to view reports.";
  }
  return "Could not load reports. Please try again.";
}

function maxCount(items: { count: number }[]): number {
  return items.reduce((max, item) => Math.max(max, item.count), 0) || 1;
}

export default function ReportsDashboard() {
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [result, setResult] = useState<Result | null>(null);

  const key = `${dateFrom}|${dateTo}`;

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getTicketsPerDay({ dateFrom: dateFrom || undefined, dateTo: dateTo || undefined }),
      getAvgFirstResponse({ dateFrom: dateFrom || undefined, dateTo: dateTo || undefined }),
    ])
      .then(([ticketsPerDay, avgFirstResponse]) => {
        if (!cancelled) setResult({ key, ticketsPerDay, avgFirstResponse });
      })
      .catch((err) => {
        if (!cancelled) setResult({ key, error: errorMessage(err) });
      });
    return () => {
      cancelled = true;
    };
  }, [key, dateFrom, dateTo]);

  const isCurrent = result?.key === key;
  const loading = !isCurrent;
  const ticketsPerDay = isCurrent ? result.ticketsPerDay : undefined;
  const avgFirstResponse = isCurrent ? result.avgFirstResponse : undefined;
  const error = isCurrent ? result.error : undefined;
  const hasFilters = dateFrom !== "" || dateTo !== "";

  const chartMax = ticketsPerDay ? maxCount(ticketsPerDay.items) : 1;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-2xl font-semibold">Reports</h1>

        <div className="flex flex-wrap items-end gap-2">
          <label className="text-sm text-gray-600">
            <span className="mb-1 block">From</span>
            <input
              type="date"
              className="rounded border border-gray-300 px-3 py-2 text-sm"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
          </label>

          <label className="text-sm text-gray-600">
            <span className="mb-1 block">To</span>
            <input
              type="date"
              className="rounded border border-gray-300 px-3 py-2 text-sm"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
            />
          </label>

          {hasFilters && (
            <button
              className="rounded border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
              onClick={() => {
                setDateFrom("");
                setDateTo("");
              }}
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      <p className="text-xs text-gray-500">
        Date filters use whole days in UTC.
      </p>

      {error && <p className="rounded bg-red-50 p-3 text-sm text-red-700">{error}</p>}

      {loading && !error && <p className="text-sm text-gray-500">Loading reports...</p>}

      {!loading && !error && (
        <div className="grid gap-6 md:grid-cols-2">
          <div className="rounded border border-gray-200 p-4">
            <h2 className="mb-4 text-lg font-medium">Tickets per day</h2>
            {ticketsPerDay && ticketsPerDay.items.length === 0 ? (
              <p className="rounded border border-dashed border-gray-300 p-6 text-center text-gray-500">
                No tickets in this range.
              </p>
            ) : (
              <div className="flex h-48 items-end gap-1">
                {ticketsPerDay?.items.map((item) => (
                  <div
                    key={item.day}
                    className="flex flex-1 flex-col items-center justify-end gap-1"
                    title={`${item.day}: ${item.count} ticket${item.count === 1 ? "" : "s"}`}
                  >
                    <span className="text-xs text-gray-600">{item.count}</span>
                    <div
                      className="w-full rounded-t bg-blue-500"
                      style={{ height: `${(item.count / chartMax) * 100}%` }}
                    />
                    <span className="w-full truncate text-center text-[10px] text-gray-500">
                      {item.day.slice(5)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="rounded border border-gray-200 p-4">
            <h2 className="mb-4 text-lg font-medium">Average first response time</h2>
            {avgFirstResponse && avgFirstResponse.ticket_count === 0 ? (
              <p className="rounded border border-dashed border-gray-300 p-6 text-center text-gray-500">
                No tickets with a first reply in this range.
              </p>
            ) : (
              <div className="flex flex-col items-center justify-center py-8">
                <span className="text-5xl font-semibold text-blue-600">
                  {avgFirstResponse?.average_hours}
                </span>
                <span className="mt-2 text-sm text-gray-600">hours, on average</span>
                <span className="mt-4 text-xs text-gray-500">
                  based on {avgFirstResponse?.ticket_count} ticket
                  {avgFirstResponse?.ticket_count === 1 ? "" : "s"}
                </span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}