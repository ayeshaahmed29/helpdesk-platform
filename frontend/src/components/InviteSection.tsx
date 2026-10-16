import { useEffect, useState, type FormEvent } from "react";

import { apiErrorMessage } from "../api/errors";
import { createInvite, listInvites, type InviteItem } from "../api/invites";
import { assignableRoles, roleLabel } from "../auth/roles";
import type { Role } from "../auth/types";

interface InviteSectionProps {
  currentRole: Role;
}

export default function InviteSection({ currentRole }: InviteSectionProps) {
  const roles = assignableRoles(currentRole);

  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("agent");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [invites, setInvites] = useState<InviteItem[]>([]);
  const [loadedKey, setLoadedKey] = useState<number | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    listInvites()
      .then((data) => {
        if (cancelled) return;
        setInvites(data);
        setLoadError(null);
        setLoadedKey(reloadKey);
      })
      .catch((err) => {
        if (cancelled) return;
        setLoadError(apiErrorMessage(err, "Could not load the invites. Please try again."));
        setLoadedKey(reloadKey);
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const loading = loadedKey !== reloadKey && invites.length === 0;
  const pending = invites.filter((invite) => invite.status === "pending");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    setNotice(null);

    const trimmed = email.trim();
    if (trimmed === "" || !trimmed.includes("@")) {
      setFormError("Please enter a valid email address.");
      return;
    }

    setSubmitting(true);
    try {
      await createInvite({ email: trimmed, role });
      setNotice(`Invite sent to ${trimmed.toLowerCase()} as ${roleLabel(role)}.`);
      setEmail("");
      setReloadKey((k) => k + 1);
    } catch (err) {
      setFormError(
        apiErrorMessage(err, "Could not send the invite. Please try again.", {
          422: "Please enter a valid email address and a role.",
          502: "The invite email could not be sent. Nothing was saved, so you can try again.",
        }),
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold">Invite someone</h2>

      <form
        onSubmit={handleSubmit}
        className="space-y-3 rounded-lg border border-gray-200 bg-white p-4"
      >
        <div className="flex flex-wrap items-end gap-3">
          <label className="block flex-1 text-sm text-gray-700" style={{ minWidth: "14rem" }}>
            <span className="mb-1 block font-medium">Email</span>
            <input
              type="email"
              autoComplete="off"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
            />
          </label>

          <label className="block text-sm text-gray-700">
            <span className="mb-1 block font-medium">Role</span>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as Role)}
              className="rounded border border-gray-300 px-3 py-2 text-sm"
            >
              {roles.map((r) => (
                <option key={r} value={r}>
                  {roleLabel(r)}
                </option>
              ))}
            </select>
          </label>

          <button
            type="submit"
            disabled={submitting}
            className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {submitting ? "Sending..." : "Send invite"}
          </button>
        </div>

        {formError && <p className="rounded bg-red-50 p-3 text-sm text-red-700">{formError}</p>}
        {notice && <p className="rounded bg-green-50 p-3 text-sm text-green-800">{notice}</p>}
      </form>

      <h3 className="text-base font-semibold">Pending invites</h3>

      {loadError && <p className="rounded bg-red-50 p-3 text-sm text-red-700">{loadError}</p>}
      {loading && <p className="text-sm text-gray-500">Loading invites...</p>}

      {!loading && !loadError && pending.length === 0 && (
        <p className="rounded border border-dashed border-gray-300 p-4 text-center text-sm text-gray-500">
          No pending invites.
        </p>
      )}

      {pending.length > 0 && (
        <div className="overflow-x-auto rounded border border-gray-200 bg-white">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50 text-left text-gray-600">
              <tr>
                <th className="px-4 py-2">Email</th>
                <th className="px-4 py-2">Role</th>
                <th className="px-4 py-2">Sent</th>
                <th className="px-4 py-2">Expires</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {pending.map((invite) => (
                <tr key={invite.id} className="hover:bg-gray-50">
                  <td className="px-4 py-2">{invite.email}</td>
                  <td className="px-4 py-2">{roleLabel(invite.role)}</td>
                  <td className="whitespace-nowrap px-4 py-2 text-gray-600">
                    {new Date(invite.created_at).toLocaleDateString()}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2 text-gray-600">
                    {new Date(invite.expires_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}