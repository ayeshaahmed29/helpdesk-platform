import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";

import {
  getTicket,
  updateTicket,
  type Ticket,
  type TicketStatus,
  type TicketPriority,
} from "../api/tickets";

const TRANSITIONS: Record<TicketStatus, TicketStatus[]> = {
  new: ["open"],
  open: ["pending", "resolved"],
  pending: ["open", "resolved"],
  resolved: ["closed", "open"],
  closed: ["open"],
};

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

type State =
  | { phase: "loading" }
  | { phase: "error"; message: string }
  | { phase: "ready"; ticket: Ticket; saving: boolean; saveError: string | null };

export default function TicketDetail() {
  const { id } = useParams<{ id: string }>();
  const ticketId = Number(id);

  const [state, setState] = useState<State>({ phase: "loading" });

   useEffect(() => {
    let cancelled = false;
    getTicket(ticketId)
      .then((ticket) => {
        if (!cancelled)
          setState({ phase: "ready", ticket, saving: false, saveError: null });
      })
      .catch(() => {
        if (!cancelled)
          setState({ phase: "error", message: "Ticket not found or you do not have access." });
      });
    return () => {
      cancelled = true;
    };
  }, [ticketId]);

  function handleStatusChange(newStatus: TicketStatus) {
    if (state.phase !== "ready") return;
    setState({ ...state, saving: true, saveError: null });
    updateTicket(ticketId, { status: newStatus })
      .then((ticket) =>
        setState({ phase: "ready", ticket, saving: false, saveError: null })
      )
      .catch(() =>
        setState({ ...state, saving: false, saveError: "Could not update status. Please try again." })
      );
  }

  if (state.phase === "loading") {
    return <p className="text-sm text-gray-500">Loading ticket...</p>;
  }

  if (state.phase === "error") {
    return (
      <div className="space-y-3">
        <Link to="/tickets" className="text-sm text-blue-600 hover:underline">
          &larr; Back to tickets
        </Link>
        <p className="rounded bg-red-50 p-3 text-sm text-red-700">{state.message}</p>
      </div>
    );
  }

  const { ticket, saving, saveError } = state;
  const allowedStatuses = TRANSITIONS[ticket.status] ?? [];

  return (
    <div className="space-y-6">
      <Link to="/tickets" className="text-sm text-blue-600 hover:underline">
        &larr; Back to tickets
      </Link>

      <div className="rounded border border-gray-200 bg-white p-6 shadow-sm space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h1 className="text-xl font-semibold text-gray-900">{ticket.subject}</h1>
          <span className="text-sm text-gray-400">#{ticket.id}</span>
        </div>

        <p className="text-gray-700 whitespace-pre-wrap">{ticket.description}</p>

        <div className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
          <div>
            <p className="text-gray-500 mb-1">Status</p>
            <span className={`rounded px-2 py-1 text-xs ${statusStyles[ticket.status]}`}>
              {ticket.status}
            </span>
          </div>
          <div>
            <p className="text-gray-500 mb-1">Priority</p>
            <span className={priorityStyles[ticket.priority]}>{ticket.priority}</span>
          </div>
          <div>
            <p className="text-gray-500 mb-1">Assignee</p>
            <span className="text-gray-800">
              {ticket.assignee_id ? `User #${ticket.assignee_id}` : "Unassigned"}
            </span>
          </div>
          <div>
            <p className="text-gray-500 mb-1">Created</p>
            <span className="text-gray-800">
              {new Date(ticket.created_at).toLocaleDateString()}
            </span>
          </div>
        </div>

        {allowedStatuses.length > 0 && (
          <div className="border-t border-gray-100 pt-4 space-y-2">
            <p className="text-sm text-gray-500">Change status</p>
            <div className="flex flex-wrap gap-2">
              {allowedStatuses.map((s) => (
                <button
                  key={s}
                  disabled={saving}
                  onClick={() => handleStatusChange(s)}
                  className="rounded border border-gray-300 px-3 py-1 text-sm hover:bg-gray-50 disabled:opacity-40"
                >
                  {s}
                </button>
              ))}
            </div>
            {saving && <p className="text-xs text-gray-500">Saving...</p>}
            {saveError && <p className="text-xs text-red-600">{saveError}</p>}
          </div>
        )}
      </div>
    </div>
  );
}