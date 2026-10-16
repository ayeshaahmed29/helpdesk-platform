import { ApiError } from "./client";

// Turns an API error into a clear message for the user.
// For 403 and 409 the backend's own text is used, because it says the exact reason.
// Pass `overrides` when a page needs a different text for one status.
export function apiErrorMessage(
  err: unknown,
  fallback: string,
  overrides: Partial<Record<number, string>> = {},
): string {
  if (err instanceof ApiError) {
    const override = overrides[err.status];
    if (override) return override;

    if ((err.status === 403 || err.status === 409) && err.detail) return err.detail;
    if (err.status === 403) return "You do not have permission to do this.";
    if (err.status === 404) return "This item was not found. It may have been removed.";
    if (err.status === 409) return "This change conflicts with the current data.";
    if (err.status === 422) return "Some values are not valid. Please check them and try again.";
    if (err.status === 503) return "The service is temporarily unavailable. Please try again.";
  }
  return fallback;
}