import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, type Location } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/useAuth";

function loginMessage(status: number | undefined): string {
  if (status === 401) return "Wrong email or password.";
  if (status === 422) return "Please enter a valid email address and your password.";
  if (status === 503) return "The service is temporarily unavailable. Please try again.";
  return "Could not log in. Please try again.";
}

export default function Login() {
  const { user, loading, login } = useAuth();
  const location = useLocation();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // The guard sends people here with the page they wanted in state.from
  const from = (location.state as { from?: Location } | null)?.from;
  const destination =
    from && from.pathname !== "/login"
      ? `${from.pathname}${from.search}${from.hash}`
      : "/tickets";

  if (loading) {
    return <div className="p-6 text-gray-500">Loading…</div>;
  }
  if (user) {
    return <Navigate to={destination} replace />;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);

    if (email.trim() === "" || password === "") {
      setFormError("Please enter your email and password.");
      return;
    }

    setSubmitting(true);
    try {
      // when this works, user is set and the redirect above runs
      await login(email.trim(), password);
    } catch (err) {
      setFormError(loginMessage(err instanceof ApiError ? err.status : undefined));
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 p-4">
      <div className="w-full max-w-md space-y-4 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-semibold">Log in</h1>

        <form onSubmit={handleSubmit} className="space-y-4">
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

          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                Password
              </label>
              <Link to="/forgot-password" className="text-sm text-indigo-600 hover:underline">
                Forgot password?
              </Link>
            </div>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              maxLength={128}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
            />
          </div>

          {formError && <p className="rounded bg-red-50 p-3 text-sm text-red-700">{formError}</p>}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {submitting ? "Logging in..." : "Log in"}
          </button>
        </form>

        <p className="text-sm text-gray-600">
          New here?{" "}
          <Link to="/signup" className="text-indigo-600 hover:underline">
            Create a company account
          </Link>
        </p>
      </div>
    </div>
  );
}