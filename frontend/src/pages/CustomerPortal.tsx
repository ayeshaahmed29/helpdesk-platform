import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import {
  createTicket,
  listTickets,
  type Ticket,
  type TicketPage,
  type TicketStatus,
} from "../api/tickets";
import { ApiError } from "../api/client";

const PAGE_SIZE = 20;

const statusStyles: Record<TicketStatus, string> = {
  new: "bg-blue-100 text-blue-800",
  open: "bg-yellow-100 text-yellow-800",
  pending: "bg-purple-100 text-purple-800",
  resolved: "bg-green-100 text-green-800",
  closed: "bg-gray-200 text-gray-700",
};

type Result = { key: string; data?: TicketPage; error?: string };

function listErrorMessage(): string {
  return "Could not load your tickets. Please try again.";
}

function submitErrorMessage(err: unknown): string {
  if (err instanceof ApiError && err.status === 422) {
    return "Please fill in both the subject and description.";
  }
  return "Could not submit your ticket. Please try again.";
}

export default function CustomerPortal() {
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState<Ticket | null>(null);

  const [page, setPage] = useState(1);
  const [refreshKey, setRefreshKey] = useState(0);
  const [result, setResult] = useState<Result | null>(null);

  const key = `${page}|${refreshKey}`;

  useEffect(() => {
    let cancelled = false;
    listTickets({ page, pageSize: PAGE_SIZE })
      .then((data) => {
        if (!cancelled) setResult({ key, data });
      })
      .catch(() => {
        if (!cancelled) setResult({ key, error: listErrorMessage() });
      });
    return () => {
      cancelled = true;
    };
  }, [key, page]);

  const isCurrent = result?.key === key;
  const loading = !isCurrent;
  const data = isCurrent ? result.data : undefined;
  const listError = isCurrent ? result.error : undefined;
  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

   async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitError(null);
    setSubmitSuccess(null);

    const trimmedSubject = subject.trim();
    const trimmedDescription = description.trim();
    if (!trimmedSubject || !trimmedDescription) {
      setSubmitError("Please fill in both the subject and description.");
      return;
    }

    setSubmitting(true);
    try {
      const ticket = await createTicket({
        subject: trimmedSubject,
        description: trimmedDescription,
      });
      setSubmitSuccess(ticket);
      setSubject("");
      setDescription("");
      setPage(1);
      setRefreshKey((k) => k + 1);
    } catch (err) {
      setSubmitError(submitErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">My tickets</h1>

      <form
        onSubmit={handleSubmit}
        className="space-y-3 rounded border border-gray-200 p-4"
      >
        <h2 className="text-lg font-medium">Submit a new ticket</h2>

        <div>
          <label className="mb-1 block text-sm text-gray-600" htmlFor="subject">
            Subject
          </label>
          <input
            id="subject"
            type="text"
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            maxLength={255}
            disabled={submitting}
          />
        </div>

        <div>
          <label className="mb-1 block text-sm text-gray-600" htmlFor="description">
            Description
          </label>
          <textarea
            id="description"
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
            rows={4}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            disabled={submitting}
          />
        </div>

        {submitError && (
          <p className="rounded bg-red-50 p-3 text-sm text-red-700">{submitError}</p>
        )}

        {submitSuccess && (
          <p className="rounded bg-green-50 p-3 text-sm text-green-700">
            Ticket #{submitSuccess.id} submitted successfully.
          </p>
        )}

        <button
          type="submit"
          className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          disabled={submitting}
        >
          {submitting ? "Submitting..." : "Submit ticket"}
        </button>
      </form>

      <div className="space-y-3">
        <h2 className="text-lg font-medium">Your tickets</h2>

        {listError && (
          <p className="rounded bg-red-50 p-3 text-sm text-red-700">{listError}</p>
        )}

        {loading && !listError && (
          <p className="text-sm text-gray-500">Loading your tickets...</p>
        )}

        {data && data.items.length === 0 && (
          <p className="rounded border border-dashed border-gray-300 p-6 text-center text-gray-500">
            You have not submitted any tickets yet.
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
                  <th className="px-4 py-2">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data.items.map((ticket) => (
                  <tr key={ticket.id} className="hover:bg-gray-50">
                    <td className="px-4 py-2 text-gray-500">{ticket.id}</td>
                    <td className="px-4 py-2">
                      <Link
                        to={`/tickets/${ticket.id}`}
                        className="text-blue-600 hover:underline"
                      >
                        {ticket.subject}
                      </Link>
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className={`rounded px-2 py-1 text-xs ${statusStyles[ticket.status]}`}
                      >
                        {ticket.status}
                      </span>
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
    </div>
  );
}