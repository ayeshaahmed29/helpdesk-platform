import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { forgotPassword } from "../api/auth";
import { ApiError } from "../api/client";

function forgotMessage(status: number | undefined): string {
  if (status === 422) return "Please enter a valid email address.";
  return "Something went wrong. Please try again.";
}

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [sentMessage, setSentMessage] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);

    if (email.trim() === "") {
      setFormError("Please enter your email.");
      return;
    }

    setSubmitting(true);
    try {
      const response = await forgotPassword(email.trim());
      setSentMessage(response.message);
    } catch (err) {
      setFormError(forgotMessage(err instanceof ApiError ? err.status : undefined));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 p-4">
      <div className="w-full max-w-md space-y-4 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-semibold">Forgot your password?</h1>

        {sentMessage ? (
          <div className="space-y-3">
            <p className="rounded bg-green-50 p-3 text-sm text-green-800">{sentMessage}</p>
            <p className="text-sm text-gray-600">
              The link works for 60 minutes. Check your spam folder if you do not see the email.
            </p>
            <Link to="/login" className="text-sm text-indigo-600 hover:underline">
              Back to login
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <p className="text-sm text-gray-600">
              Enter your email and we will send you a link to choose a new password.
            </p>

            <div className="space-y-1">
              <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
              />
            </div>

            {formError && <p className="rounded bg-red-50 p-3 text-sm text-red-700">{formError}</p>}

            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {submitting ? "Sending..." : "Send reset link"}
            </button>

            <Link to="/login" className="block text-sm text-indigo-600 hover:underline">
              Back to login
            </Link>
          </form>
        )}
      </div>
    </div>
  );
}