import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../api/client";
import { acceptInvite, getInvite, type InvitePreview } from "../api/invites";

type Result = { token: string; invite?: InvitePreview; errorStatus?: number };

function lookupMessage(status: number | undefined): string {
  if (status === 404) return "This invite link is not valid. Please ask for a new invite.";
  if (status === 410) {
    return "This invite has expired or was already used. Please ask for a new invite.";
  }
  return "Could not load the invite. Please try again.";
}

function acceptMessage(status: number | undefined): string {
  if (status === 404) return "This invite link is not valid. Please ask for a new invite.";
  if (status === 410) {
    return "This invite has expired or was already used. Please ask for a new invite.";
  }
  if (status === 409) return "An account with this email already exists. Try logging in.";
  if (status === 422) return "Please check your details. The password needs 8 to 128 characters.";
  return "Could not create your account. Please try again.";
}

export default function AcceptInvite() {
  const { token = "" } = useParams<{ token: string }>();

  const [result, setResult] = useState<Result | null>(null);
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    getInvite(token)
      .then((invite) => {
        if (!cancelled) setResult({ token, invite });
      })
      .catch((err) => {
        const errorStatus = err instanceof ApiError ? err.status : undefined;
        if (!cancelled) setResult({ token, errorStatus });
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const isCurrent = result?.token === token;
  const loading = token !== "" && !isCurrent;
  const invite = isCurrent ? result.invite : undefined;
  const errorStatus = isCurrent ? result.errorStatus : token === "" ? 404 : undefined;
  const lookupFailed = !loading && !invite;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);

    if (fullName.trim() === "") {
      setFormError("Please enter your full name.");
      return;
    }
    if (password.length < 8) {
      setFormError("The password must be at least 8 characters.");
      return;
    }
    if (password !== confirm) {
      setFormError("The passwords do not match.");
      return;
    }

    setSubmitting(true);
    try {
      await acceptInvite(token, { full_name: fullName.trim(), password });
      setDone(true);
    } catch (err) {
      setFormError(acceptMessage(err instanceof ApiError ? err.status : undefined));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 p-4">
      <div className="w-full max-w-md space-y-4 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-semibold">Accept your invite</h1>

        {loading && <p className="text-sm text-gray-500">Loading invite...</p>}

        {lookupFailed && (
          <div className="space-y-3">
            <p className="rounded bg-red-50 p-3 text-sm text-red-700">
              {lookupMessage(errorStatus)}
            </p>
            <Link to="/login" className="text-sm text-indigo-600 hover:underline">
              Go to login
            </Link>
          </div>
        )}

        {invite && done && (
          <div className="space-y-3">
            <p className="rounded bg-green-50 p-3 text-sm text-green-800">
              Your account is ready. You joined {invite.organization_name} as {invite.role}.
            </p>
            <Link
              to="/login"
              className="inline-block rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
            >
              Go to login
            </Link>
          </div>
        )}

        {invite && !done && (
          <form onSubmit={handleSubmit} className="space-y-4">
            <p className="text-sm text-gray-600">
              You were invited to join <strong>{invite.organization_name}</strong> as{" "}
              <strong>{invite.role}</strong>. Choose your name and password to create your
              account.
            </p>

            <div className="space-y-1">
              <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                Email
              </label>
              <input
                id="email"
                type="email"
                value={invite.email}
                readOnly
                className="w-full rounded border border-gray-300 bg-gray-100 px-3 py-2 text-sm text-gray-600"
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="full_name" className="block text-sm font-medium text-gray-700">
                Full name
              </label>
              <input
                id="full_name"
                type="text"
                autoComplete="name"
                maxLength={100}
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="new-password"
                maxLength={128}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
              />
              <p className="text-xs text-gray-500">At least 8 characters.</p>
            </div>

            <div className="space-y-1">
              <label htmlFor="confirm" className="block text-sm font-medium text-gray-700">
                Confirm password
              </label>
              <input
                id="confirm"
                type="password"
                autoComplete="new-password"
                maxLength={128}
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
              />
            </div>

            {formError && <p className="rounded bg-red-50 p-3 text-sm text-red-700">{formError}</p>}

            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {submitting ? "Creating account..." : "Create account"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}