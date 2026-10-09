import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { listAuditLogs, type AuditLogPage } from "../api/auditLogs";
import { ApiError } from "../api/client";

// Must match the AuditAction enum in backend/core/audit.py.
// When a new action is added there, add it here too.
const ACTIONS = [
  "user.signup",
  "user.login",
  "user.password_reset_requested",
  "user.password_reset",
  "invite.created",
  "invite.accepted",
  "ticket.created",
  "ticket.updated",
  "ticket.status_changed",
];
const PAGE_SIZE = 20;

type Result = { key: string; data?: AuditLogPage; error?: string };

function formatValue(value: unknown): string {
  if (Array.isArray(value)) return value.map(formatValue).join(" → ");
  if (value !== null && typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function formatDetails(metadata: Record<string, unknown>): string {
  const entries = Object.entries(metadata);
  if (entries.length === 0) return "-";
  return entries.map(([k, v]) => `${k}: ${formatValue(v)}`).join(", ");
}

function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 400) return "The start date must not be after the end date.";
    if (err.status === 403) return "You do not have permission to view the audit log.";
  }
  return "Could not load the audit log. Please try again.";
}

export default function AuditLog() {
  const [action, setAction] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<Result | null>(null);

  const key = `${action}|${dateFrom}|${dateTo}|${page}`;

  useEffect(() => {
    let cancelled = false;
    listAuditLogs({
      action: action || undefined,
      dateFrom: dateFrom || undefined,
      dateTo: dateTo || undefined,
      page,
      pageSize: PAGE_SIZE,
    })
      .then((data) => {
        if (!cancelled) setResult({ key, data });
      })
      .catch((err) => {
        if (!cancelled) setResult({ key, error: errorMessage(err) });
      });
    return () => {
      cancelled = true;
    };
  }, [key, action, dateFrom, dateTo, page]);

  const isCurrent = result?.key === key;
  const loading = !isCurrent;
  const data = isCurrent ? result.data : undefined;
  const error = isCurrent ? result.error : undefined;
  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;
  const hasFilters = action !== "" || dateFrom !== "" || dateTo !== "";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-2xl font-semibold">Audit log</h1>

        <div className="flex flex-wrap items-end gap-2">
          <label className="text-sm text-gray-600">
            <span className="mb-1 block">Action</span>
            <select
              className="rounded border border-gray-300 px-3 py-2 text-sm"
              value={action}
              onChange={(e) => {
                setAction(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All actions</option>
              {ACTIONS.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </label>

          <label className="text-sm text-gray-600">
            <span className="mb-1 block">From</span>
            <input
              type="date"
              className="rounded border border-gray-300 px-3 py-2 text-sm"
              value={dateFrom}
              onChange={(e) => {
                setDateFrom(e.target.value);
                setPage(1);
              }}
            />
          </label>

          <label className="text-sm text-gray-600">
            <span className="mb-1 block">To</span>
            <input
              type="date"
              className="rounded border border-gray-300 px-3 py-2 text-sm"
              value={dateTo}
              onChange={(e) => {
                setDateTo(e.target.value);
                setPage(1);
              }}
            />
          </label>

          {hasFilters && (
            <button
              className="rounded border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
              onClick={() => {
                setAction("");
                setDateFrom("");
                setDateTo("");
                setPage(1);
              }}
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      <p className="text-xs text-gray-500">
        Date filters use whole days in UTC. Times in the table are shown in your local time.
      </p>

      {error && <p className="rounded bg-red-50 p-3 text-sm text-red-700">{error}</p>}

      {loading && <p className="text-sm text-gray-500">Loading audit log...</p>}

      {data && data.items.length === 0 && (
        <p className="rounded border border-dashed border-gray-300 p-6 text-center text-gray-500">
          No audit entries match these filters.
        </p>
      )}

      {data && data.items.length > 0 && (
        <div className="overflow-x-auto rounded border border-gray-200">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50 text-left text-gray-600">
              <tr>
                <th className="px-4 py-2">Time</th>
                <th className="px-4 py-2">Actor</th>
                <th className="px-4 py-2">Action</th>
                <th className="px-4 py-2">Entity</th>
                <th className="px-4 py-2">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.items.map((item) => (
                <tr key={item.id} className="hover:bg-gray-50">
                  <td className="whitespace-nowrap px-4 py-2 text-gray-600">
                    {new Date(item.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2">
                    {item.actor_name ?? <span className="text-gray-500">System</span>}
                  </td>
                  <td className="px-4 py-2">
                    <span className="rounded bg-gray-100 px-2 py-1 font-mono text-xs text-gray-800">
                      {item.action}
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    {item.entity_type === "ticket" && item.entity_id ? (
                      <Link
                        to={`/tickets/${item.entity_id}`}
                        className="text-blue-600 hover:underline"
                      >
                        ticket #{item.entity_id}
                      </Link>
                    ) : item.entity_type ? (
                      <span className="text-gray-700">
                        {item.entity_type}
                        {item.entity_id ? ` #${item.entity_id}` : ""}
                      </span>
                    ) : (
                      <span className="text-gray-400">-</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-gray-600">{formatDetails(item.metadata)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && data.total > 0 && (
        <div className="flex items-center justify-between text-sm text-gray-600">
          <span>
            {data.total} entr{data.total === 1 ? "y" : "ies"}, page {page} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              className="rounded border border-gray-300 px-3 py-1 disabled:opacity-40"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </button>
            <button
              className="rounded border border-gray-300 px-3 py-1 disabled:opacity-40"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}