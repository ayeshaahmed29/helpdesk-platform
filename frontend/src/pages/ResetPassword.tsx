import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { resetPassword } from "../api/auth";
import { ApiError } from "../api/client";

// 404 and 410 mean the link itself cannot be used, so the form is hidden
function linkProblem(status: number | undefined): string | null {
  if (status === 404) return "This reset link is not valid. Please ask for a new one.";
  if (status === 410) {
    return "This reset link has expired or was already used. Please ask for a new one.";
  }
  return null;
}

function resetMessage(status: number | undefined): string {
  if (status === 422) return "Please check your password. It needs 8 to 128 characters.";
  return "Could not change your password. Please try again.";
}

export default function ResetPassword() {
  const { token = "" } = useParams<{ token: string }>();

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [badLink, setBadLink] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);

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
      await resetPassword(token, password);
      setDone(true);
    } catch (err) {
      const status = err instanceof ApiError ? err.status : undefined;
      const problem = linkProblem(status);
      if (problem) {
        setBadLink(problem);
      } else {
        setFormError(resetMessage(status));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 p-4">
      <div className="w-full max-w-md space-y-4 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-semibold">Choose a new password</h1>

        {done && (
          <div className="space-y-3">
            <p className="rounded bg-green-50 p-3 text-sm text-green-800">
              Your password has been changed. You can now log in with the new password.
            </p>
            <Link
              to="/login"
              className="inline-block rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
            >
              Go to login
            </Link>
          </div>
        )}

        {!done && badLink && (
          <div className="space-y-3">
            <p className="rounded bg-red-50 p-3 text-sm text-red-700">{badLink}</p>
            <Link
              to="/forgot-password"
              className="inline-block rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
            >
              Ask for a new link
            </Link>
          </div>
        )}

        {!done && !badLink && (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1">
              <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                New password
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
                Confirm new password
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
              {submitting ? "Saving..." : "Change password"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}