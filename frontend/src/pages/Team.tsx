import { useEffect, useState } from "react";

import { ApiError } from "../api/client";
import { apiErrorMessage } from "../api/errors";
import { listUsers, updateUser, type TeamUser, type UserUpdate } from "../api/users";
import { assignableRoles, roleLabel } from "../auth/roles";
import type { Role } from "../auth/types";
import { useAuth } from "../auth/useAuth";
import ConfirmDialog from "../components/ConfirmDialog";
import InviteSection from "../components/InviteSection";

export default function Team() {
  const { user: me } = useAuth();

  const [users, setUsers] = useState<TeamUser[]>([]);
  const [loadedKey, setLoadedKey] = useState<number | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [busyId, setBusyId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [pendingDeactivate, setPendingDeactivate] = useState<TeamUser | null>(null);

  useEffect(() => {
    let cancelled = false;
    listUsers()
      .then((data) => {
        if (cancelled) return;
        setUsers(data);
        setLoadError(null);
        setLoadedKey(reloadKey);
      })
      .catch((err) => {
        if (cancelled) return;
        setLoadError(
          apiErrorMessage(err, "Could not load the team. Please try again.", {
            403: "You do not have permission to view the team.",
          }),
        );
        setLoadedKey(reloadKey);
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  if (!me) return null;

  const loading = loadedKey !== reloadKey && users.length === 0;
  const myRoles = assignableRoles(me.role);
  const activeOwners = users.filter((u) => u.role === "owner" && u.is_active).length;

  // Why a row is locked, or null when the actions are allowed.
  // This only hides and disables things. The backend checks every rule again.
  function lockReason(target: TeamUser): string | null {
    if (target.id === me!.id) {
      return "You cannot change your own role or deactivate yourself.";
    }
    if (me!.role !== "owner" && target.role === "owner") {
      return "Only an owner can change an owner.";
    }
    if (target.role === "owner" && target.is_active && activeOwners <= 1) {
      return "The last active owner cannot be changed.";
    }
    return null;
  }

  async function applyChange(target: TeamUser, data: UserUpdate, okMessage: string) {
    setActionError(null);
    setNotice(null);
    setBusyId(target.id);
    try {
      const updated = await updateUser(target.id, data);
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
      setNotice(okMessage);
    } catch (err) {
      setActionError(apiErrorMessage(err, "Could not save the change. Please try again."));
      // The data may be out of date (user removed, roles changed): load it again
      if (err instanceof ApiError && [403, 404, 409].includes(err.status)) {
        setReloadKey((k) => k + 1);
      }
    } finally {
      setBusyId(null);
    }
  }

  function displayName(target: TeamUser): string {
    return target.full_name || target.email;
  }

  function handleRoleChange(target: TeamUser, newRole: Role) {
    if (newRole === target.role) return;
    void applyChange(
      target,
      { role: newRole },
      `${displayName(target)} is now ${roleLabel(newRole)}.`,
    );
  }

  function confirmDeactivate() {
    const target = pendingDeactivate;
    setPendingDeactivate(null);
    if (!target) return;
    void applyChange(target, { is_active: false }, `${displayName(target)} was deactivated.`);
  }

  return (
    <div className="space-y-8">
      <section className="space-y-4">
        <h1 className="text-2xl font-semibold">Team</h1>

        {loadError && <p className="rounded bg-red-50 p-3 text-sm text-red-700">{loadError}</p>}
        {actionError && <p className="rounded bg-red-50 p-3 text-sm text-red-700">{actionError}</p>}
        {notice && <p className="rounded bg-green-50 p-3 text-sm text-green-800">{notice}</p>}

        {loading && <p className="text-sm text-gray-500">Loading team...</p>}

        {users.length > 0 && (
          <div className="overflow-x-auto rounded border border-gray-200 bg-white">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50 text-left text-gray-600">
                <tr>
                  <th className="px-4 py-2">Name</th>
                  <th className="px-4 py-2">Email</th>
                  <th className="px-4 py-2">Role</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {users.map((target) => {
                  const lock = lockReason(target);
                  const busy = busyId === target.id;
                  // Always show the current role, even if this user may not assign it
                  const options = myRoles.includes(target.role)
                    ? myRoles
                    : [target.role, ...myRoles];

                  return (
                    <tr key={target.id} className="hover:bg-gray-50">
                      <td className="px-4 py-2">
                        {target.full_name ?? <span className="text-gray-400">-</span>}
                        {target.id === me.id && <span className="ml-2 text-gray-500">(you)</span>}
                      </td>
                      <td className="px-4 py-2">{target.email}</td>
                      <td className="px-4 py-2">
                        <select
                          aria-label={`Role of ${displayName(target)}`}
                          value={target.role}
                          disabled={lock !== null || busy}
                          title={lock ?? undefined}
                          onChange={(e) => handleRoleChange(target, e.target.value as Role)}
                          className="rounded border border-gray-300 px-2 py-1 text-sm disabled:bg-gray-100 disabled:text-gray-500"
                        >
                          {options.map((r) => (
                            <option key={r} value={r}>
                              {roleLabel(r)}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-4 py-2">
                        {target.is_active ? (
                          <span className="rounded bg-green-100 px-2 py-1 text-xs text-green-800">
                            Active
                          </span>
                        ) : (
                          <span className="rounded bg-gray-100 px-2 py-1 text-xs text-gray-600">
                            Inactive
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2">
                        {target.is_active ? (
                          <button
                            type="button"
                            disabled={lock !== null || busy}
                            title={lock ?? undefined}
                            onClick={() => setPendingDeactivate(target)}
                            className="rounded border border-red-300 px-3 py-1 text-sm text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-40"
                          >
                            Deactivate
                          </button>
                        ) : (
                          <button
                            type="button"
                            disabled={lock !== null || busy}
                            title={lock ?? undefined}
                            onClick={() =>
                              void applyChange(
                                target,
                                { is_active: true },
                                `${displayName(target)} was reactivated.`,
                              )
                            }
                            className="rounded border border-gray-300 px-3 py-1 text-sm text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
                          >
                            Reactivate
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <p className="text-xs text-gray-500">
          Greyed-out actions are locked. Hover over them to see why. The server checks every rule
          again.
        </p>
      </section>

      <InviteSection currentRole={me.role} />

      {pendingDeactivate && (
        <ConfirmDialog
          title="Deactivate this user?"
          message={`${displayName(pendingDeactivate)} will not be able to log in or use the app. You can reactivate the account later.`}
          confirmLabel="Deactivate"
          onConfirm={confirmDeactivate}
          onCancel={() => setPendingDeactivate(null)}
        />
      )}
    </div>
  );
}