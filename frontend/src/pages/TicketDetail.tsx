import { useEffect, useRef, useState } from "react";
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
import { listTags, addTagToTicket, removeTagFromTicket, type Tag } from "../api/tags";
import {
  listAttachments,
  uploadAttachment,
  downloadAttachment,
  type Attachment,
} from "../api/attachments";

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

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

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

  const [allTags, setAllTags] = useState<Tag[]>([]);
  const [ticketTags, setTicketTags] = useState<Tag[]>([]);
  const [showTagDropdown, setShowTagDropdown] = useState(false);

  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let cancelled = false;
    getTicket(ticketId)
      .then((ticket) => {
        if (!cancelled) {
          setState({ phase: "ready", ticket, saving: false, saveError: null });
          const t = ticket as Ticket & { tags?: Tag[] };
          if (t.tags) setTicketTags(t.tags);
        }
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
      .catch(() => {});
    listTags()
      .then((tags) => {
        if (!cancelled) setAllTags(tags);
      })
      .catch(() => {});
    listAttachments(ticketId)
      .then((atts) => {
        if (!cancelled) setAttachments(atts);
      })
      .catch(() => {});
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

  async function handleAddTag(tag: Tag) {
    try {
      await addTagToTicket(tag.id, ticketId);
      setTicketTags((prev) => [...prev, tag]);
      setShowTagDropdown(false);
    } catch {
      /* ignore */
    }
  }

  async function handleRemoveTag(tag: Tag) {
    try {
      await removeTagFromTicket(tag.id, ticketId);
      setTicketTags((prev) => prev.filter((t) => t.id !== tag.id));
    } catch {
      /* ignore */
    }
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    try {
      const att = await uploadAttachment(ticketId, file);
      setAttachments((prev) => [...prev, att]);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Upload failed.";
      setUploadError(msg);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
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
        getTicket(ticketId)
          .then((ticket) => {
            setState((prev) =>
              prev.phase === "ready"
                ? { phase: "ready", ticket, saving: false, saveError: null }
                : prev
            );
          })
          .catch(() => {});
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
  const isStaff = role !== null && role !== "customer";
  const allowedStatuses: TicketStatus[] =
    role === null
      ? []
      : role === "customer"
        ? ticket.status === "resolved"
          ? ["open"]
          : []
        : TRANSITIONS[ticket.status] ?? [];

  const availableTags = allTags.filter(
    (t) => !ticketTags.some((tt) => tt.id === t.id)
  );

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

        {/* Tags Section */}
        <div className="border-t border-gray-100 pt-4 space-y-2">
          <p className="text-sm text-gray-500">Tags</p>
          <div className="flex flex-wrap gap-2">
            {ticketTags.map((tag) => (
              <span
                key={tag.id}
                className="inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium text-white"
                style={{ backgroundColor: tag.color ?? "#6b7280" }}
              >
                {tag.name}
                {isStaff && (
                  <button
                    onClick={() => handleRemoveTag(tag)}
                    className="ml-1 hover:opacity-75"
                    title="Remove tag"
                  >
                    x
                  </button>
                )}
              </span>
            ))}
            {ticketTags.length === 0 && (
              <span className="text-xs text-gray-400">No tags</span>
            )}
          </div>
          {isStaff && availableTags.length > 0 && (
            <div className="relative">
              <button
                onClick={() => setShowTagDropdown(!showTagDropdown)}
                className="rounded border border-gray-300 px-3 py-1 text-sm hover:bg-gray-50"
              >
                + Add tag
              </button>
              {showTagDropdown && (
                <div className="absolute z-10 mt-1 w-48 rounded border border-gray-200 bg-white shadow-lg">
                  {availableTags.map((tag) => (
                    <button
                      key={tag.id}
                      onClick={() => handleAddTag(tag)}
                      className="flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-gray-50"
                    >
                      <span
                        className="inline-block h-3 w-3 rounded-full"
                        style={{ backgroundColor: tag.color ?? "#6b7280" }}
                      />
                      {tag.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
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

      {/* Attachments Section */}
      <div className="rounded border border-gray-200 bg-white p-6 shadow-sm space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">Attachments</h2>

        {attachments.length === 0 && (
          <p className="text-sm text-gray-500">No attachments yet.</p>
        )}

        {attachments.length > 0 && (
          <ul className="divide-y divide-gray-100">
            {attachments.map((att) => (
              <li key={att.id} className="flex items-center justify-between py-2">
                <div className="text-sm">
                  <button
                    onClick={() => downloadAttachment(att.id, att.filename)}
                    className="text-blue-600 hover:underline font-medium"
                  >
                    {att.filename}
                  </button>
                  <span className="ml-2 text-gray-400">
                    {formatSize(att.size)} - {att.content_type}
                  </span>
                </div>
                <span className="text-xs text-gray-400">
                  {new Date(att.created_at).toLocaleDateString()}
                </span>
              </li>
            ))}
          </ul>
        )}

        <div className="border-t border-gray-100 pt-3">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            disabled={uploading}
            className="text-sm"
          />
          {uploading && <p className="text-xs text-gray-500 mt-1">Uploading...</p>}
          {uploadError && <p className="text-xs text-red-600 mt-1">{uploadError}</p>}
        </div>
      </div>

      {/* Comments Section */}
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