import { useState, type FormEvent } from "react";
import { Link, Navigate } from "react-router-dom";

import { signupRequest } from "../api/auth";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/useAuth";

function signupMessage(status: number | undefined): string {
  if (status === 409) return "An account with this email already exists.";
  if (status === 422) {
    return "Please check your details. The company name needs at least 2 characters and the password 8 to 128.";
  }
  return "Could not create your account. Please try again.";
}

export default function Signup() {
  const { user, loading, login } = useAuth();

  const [organizationName, setOrganizationName] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [emailTaken, setEmailTaken] = useState(false);
  // Account was created, but the automatic login failed
  const [loginFailed, setLoginFailed] = useState(false);

  if (loading) {
    return <div className="p-6 text-gray-500">Loading…</div>;
  }
  if (user) {
    return <Navigate to="/tickets" replace />;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    setEmailTaken(false);

    if (organizationName.trim().length < 2) {
      setFormError("The company name needs at least 2 characters.");
      return;
    }
    if (fullName.trim() === "") {
      setFormError("Please enter your full name.");
      return;
    }
    if (email.trim() === "") {
      setFormError("Please enter your email.");
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
      await signupRequest({
        organization_name: organizationName.trim(),
        full_name: fullName.trim(),
        email: email.trim(),
        password,
      });
    } catch (err) {
      const status = err instanceof ApiError ? err.status : undefined;
      setEmailTaken(status === 409);
      setFormError(signupMessage(status));
      setSubmitting(false);
      return;
    }

    // The signup response has no token, so log in with the same details.
    // When this works, user is set and the redirect above runs.
    try {
      await login(email.trim(), password);
    } catch {
      setLoginFailed(true);
      setSubmitting(false);
    }
  }

  if (loginFailed) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 p-4">
        <div className="w-full max-w-md space-y-3 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h1 className="text-2xl font-semibold">Account created</h1>
          <p className="rounded bg-green-50 p-3 text-sm text-green-800">
            Your account was created, but we could not log you in automatically. Please log in
            with your new details.
          </p>
          <Link
            to="/login"
            className="inline-block rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
          >
            Go to login
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 p-4">
      <div className="w-full max-w-md space-y-4 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-semibold">Create your company account</h1>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <label htmlFor="organization_name" className="block text-sm font-medium text-gray-700">
              Company name
            </label>
            <input
              id="organization_name"
              type="text"
              autoComplete="organization"
              maxLength={100}
              value={organizationName}
              onChange={(e) => setOrganizationName(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
            />
          </div>

          <div className="space-y-1">
            <label htmlFor="full_name" className="block text-sm font-medium text-gray-700">
              Your full name
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

          {formError && (
            <p className="rounded bg-red-50 p-3 text-sm text-red-700">
              {formError}
              {emailTaken && (
                <>
                  {" "}
                  <Link to="/login" className="font-medium underline">
                    Log in instead
                  </Link>
                </>
              )}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {submitting ? "Creating account..." : "Create account"}
          </button>
        </form>

        <p className="text-sm text-gray-600">
          Already have an account?{" "}
          <Link to="/login" className="text-indigo-600 hover:underline">
            Log in
          </Link>
        </p>
      </div>
    </div>
  );
}