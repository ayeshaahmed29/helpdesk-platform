import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  listTickets,
  type TicketPage,
  type TicketPriority,
  type TicketStatus,
} from "../api/tickets";

const STATUSES: TicketStatus[] = ["new", "open", "pending", "resolved", "closed"];
const PRIORITIES: TicketPriority[] = ["low", "normal", "high", "urgent"];
const PAGE_SIZE = 20;

const statusStyles: Record<TicketStatus, string> = {
  new: "bg-blue-100 text-blue-800",
  open: "bg-yellow-100 text-yellow-800",
  pending: "bg-purple-100 text-purple-800",
  resolved: "bg-green-100 text-green-800",
  closed: "bg-gray-200 text-gray-700",
};

const priorityStyles: Record<TicketPriority, string> = {
  low: "text-gray-500",
  normal: "text-gray-800",
  high: "text-orange-600 font-medium",
  urgent: "text-red-600 font-semibold",
};

type Result = { key: string; data?: TicketPage; error?: string };

export default function TicketList() {
  const [status, setStatus] = useState<TicketStatus | "">("");
  const [priority, setPriority] = useState<TicketPriority | "">("");
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<Result | null>(null);

  const key = `${status}|${priority}|${page}`;

  useEffect(() => {
    let cancelled = false;
    listTickets({
      status: status || undefined,
      priority: priority || undefined,
      page,
      pageSize: PAGE_SIZE,
    })
      .then((data) => {
        if (!cancelled) setResult({ key, data });
      })
      .catch(() => {
        if (!cancelled) setResult({ key, error: "Could not load tickets. Please try again." });
      });
    return () => {
      cancelled = true;
    };
  }, [key, status, priority, page]);

  const isCurrent = result?.key === key;
  const loading = !isCurrent;
  const data = isCurrent ? result.data : undefined;
  const error = isCurrent ? result.error : undefined;
  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Tickets</h1>

        <div className="flex gap-2">
          <select
            className="rounded border border-gray-300 px-3 py-2 text-sm"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value as TicketStatus | "");
              setPage(1);
            }}
          >
            <option value="">All statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>

          <select
            className="rounded border border-gray-300 px-3 py-2 text-sm"
            value={priority}
            onChange={(e) => {
              setPriority(e.target.value as TicketPriority | "");
              setPage(1);
            }}
          >
            <option value="">All priorities</option>
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && <p className="rounded bg-red-50 p-3 text-sm text-red-700">{error}</p>}

      {loading && <p className="text-sm text-gray-500">Loading tickets...</p>}

      {data && data.items.length === 0 && (
        <p className="rounded border border-dashed border-gray-300 p-6 text-center text-gray-500">
          No tickets match these filters.
        </p>
      )}

      {data && data.items.length > 0 && (
        <div className="overflow-x-auto rounded border border-gray-200">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50 text-left text-gray-600">
              <tr>
                <th className="px-4 py-2">#</th>
                <th className="px-4 py-2">Subject</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Priority</th>
                <th className="px-4 py-2">Assignee</th>
                <th className="px-4 py-2">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.items.map((ticket) => (
                <tr key={ticket.id} className="hover:bg-gray-50">
                  <td className="px-4 py-2 text-gray-500">{ticket.id}</td>
                  <td className="px-4 py-2">
                    <Link to={`/tickets/${ticket.id}`} className="text-blue-600 hover:underline">
                      {ticket.subject}
                    </Link>
                  </td>
                  <td className="px-4 py-2">
                    <span className={`rounded px-2 py-1 text-xs ${statusStyles[ticket.status]}`}>
                      {ticket.status}
                    </span>
                  </td>
                  <td className={`px-4 py-2 ${priorityStyles[ticket.priority]}`}>
                    {ticket.priority}
                  </td>
                  <td className="px-4 py-2 text-gray-600">
                    {ticket.assignee_id ? `User #${ticket.assignee_id}` : "Unassigned"}
                  </td>
                  <td className="px-4 py-2 text-gray-600">
                    {new Date(ticket.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && data.total > 0 && (
        <div className="flex items-center justify-between text-sm text-gray-600">
          <span>
            {data.total} ticket{data.total === 1 ? "" : "s"}, page {page} of {totalPages}
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