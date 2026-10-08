import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";

import {
  getTicket,
  updateTicket,
  type Ticket,
  type TicketStatus,
  type TicketPriority,
} from "../api/tickets";
import {
  listComments,
  createComment,
  type Comment,
} from "../api/comments";
import { getCurrentUser, type UserRole } from "../api/auth";

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
  const [comments, setComments] = useState<Comment[]>([]);
  const [commentsError, setCommentsError] = useState<string | null>(null);
  const [body, setBody] = useState("");
  const [isInternal, setIsInternal] = useState(false);
  const [posting, setPosting] = useState(false);
  const [postError, setPostError] = useState<string | null>(null);
  const [role, setRole] = useState<UserRole | null>(null);

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
    listComments(ticketId)
      .then((c) => {
        if (!cancelled) setComments(c);
      })
      .catch(() => {
        if (!cancelled) setCommentsError("Could not load comments.");
      });
    getCurrentUser()
      .then((u) => {
        if (!cancelled) setRole(u.role);
      })
      .catch(() => {
        /* ignore */
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

  function handleCommentSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!body.trim() || posting) return;
    setPosting(true);
    setPostError(null);
    createComment(ticketId, { body: body.trim(), is_internal: isInternal })
      .then((newComment) => {
        setComments((prev) => [...prev, newComment]);
        setBody("");
        setIsInternal(false);
        return getTicket(ticketId);
      })
      .then((ticket) => {
        setState((prev) =>
          prev.phase === "ready"
            ? { phase: "ready", ticket, saving: false, saveError: null }
            : prev
        );
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : "Could not post comment.";
        setPostError(msg);
      })
      .finally(() => setPosting(false));
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
  const isStaff = role !== null && role !== "customer";

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

      <div className="rounded border border-gray-200 bg-white p-6 shadow-sm space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">Comments</h2>

        {commentsError && (
          <p className="rounded bg-red-50 p-3 text-sm text-red-700">{commentsError}</p>
        )}

        {comments.length === 0 && !commentsError && (
          <p className="text-sm text-gray-500">No comments yet.</p>
        )}

        <ul className="space-y-3">
          {comments.map((c) => (
            <li
              key={c.id}
              className={`rounded border p-3 ${
                c.is_internal
                  ? "border-yellow-200 bg-yellow-50"
                  : "border-gray-200 bg-gray-50"
              }`}
            >
              <div className="flex items-center justify-between text-xs text-gray-500 mb-2">
                <span>User #{c.author_id}</span>
                <div className="flex items-center gap-2">
                  {c.is_internal && (
                    <span className="rounded bg-yellow-200 px-2 py-0.5 text-yellow-800">
                      Internal
                    </span>
                  )}
                  <span>{new Date(c.created_at).toLocaleString()}</span>
                </div>
              </div>
              <p className="text-sm text-gray-800 whitespace-pre-wrap">{c.body}</p>
            </li>
          ))}
        </ul>

        <form onSubmit={handleCommentSubmit} className="space-y-3 border-t border-gray-100 pt-4">
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Write a reply..."
            rows={3}
            disabled={posting}
            className="w-full rounded border border-gray-300 p-2 text-sm disabled:opacity-50"
          />
          <div className="flex items-center justify-between">
            {isStaff ? (
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={isInternal}
                  onChange={(e) => setIsInternal(e.target.checked)}
                  disabled={posting}
                />
                Internal note (staff only)
              </label>
            ) : (
              <span />
            )}
            <button
              type="submit"
              disabled={posting || !body.trim()}
              className="rounded bg-blue-600 px-4 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-40"
            >
              {posting ? "Posting..." : "Post"}
            </button>
          </div>
          {postError && <p className="text-xs text-red-600">{postError}</p>}
        </form>
      </div>
    </div>
  );
}