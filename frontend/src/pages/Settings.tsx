import { useEffect, useState, type FormEvent } from "react";

import { apiErrorMessage } from "../api/errors";
import { getSlaSettings, updateSlaSettings } from "../api/settings";

const MIN_HOURS = 1;
const MAX_HOURS = 168;

export default function Settings() {
  const [saved, setSaved] = useState<number | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getSlaSettings()
      .then((data) => {
        if (cancelled) return;
        setSaved(data.first_reply_hours);
        setInput(String(data.first_reply_hours));
        setLoadError(null);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setLoadError(
          apiErrorMessage(err, "Could not load the settings. Please try again.", {
            403: "You do not have permission to view the settings.",
          }),
        );
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  function retry() {
    setLoading(true);
    setLoadError(null);
    setReloadKey((k) => k + 1);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    setNotice(null);

    const trimmed = input.trim();
    if (!/^\d+$/.test(trimmed)) {
      setFormError("Please enter a whole number of hours.");
      return;
    }
    const hours = Number(trimmed);
    if (hours < MIN_HOURS || hours > MAX_HOURS) {
      setFormError(`The number of hours must be between ${MIN_HOURS} and ${MAX_HOURS}.`);
      return;
    }

    setSaving(true);
    try {
      const result = await updateSlaSettings(hours);
      setSaved(result.first_reply_hours);
      setInput(String(result.first_reply_hours));
      setNotice(`Saved. First replies are now due within ${result.first_reply_hours} hours.`);
    } catch (err) {
      setFormError(
        apiErrorMessage(err, "Could not save the setting. Please try again.", {
          403: "You do not have permission to change the settings.",
          422: `The number of hours must be a whole number between ${MIN_HOURS} and ${MAX_HOURS}.`,
        }),
      );
    } finally {
      setSaving(false);
    }
  }

  const unchanged = saved !== null && input.trim() === String(saved);

  return (
    <div className="max-w-xl space-y-4">
      <h1 className="text-2xl font-semibold">Settings</h1>

      <section className="space-y-4 rounded-lg border border-gray-200 bg-white p-4">
        <h2 className="text-lg font-semibold">First reply SLA</h2>
        <p className="text-sm text-gray-600">
          A ticket is overdue when it gets no public reply from staff within this many hours. The
          background job flags overdue tickets and emails the owners and admins.
        </p>

        {loading && <p className="text-sm text-gray-500">Loading settings...</p>}

        {loadError && (
          <div className="space-y-2">
            <p className="rounded bg-red-50 p-3 text-sm text-red-700">{loadError}</p>
            <button
              type="button"
              className="rounded border border-gray-300 px-3 py-1 text-sm text-gray-700 hover:bg-gray-50"
              onClick={retry}
            >
              Try again
            </button>
          </div>
        )}

        {!loading && !loadError && (
          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="space-y-1">
              <label htmlFor="first_reply_hours" className="block text-sm font-medium text-gray-700">
                First reply due within (hours)
              </label>
              <input
                id="first_reply_hours"
                type="number"
                inputMode="numeric"
                min={MIN_HOURS}
                max={MAX_HOURS}
                step={1}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                className="w-32 rounded border border-gray-300 px-3 py-2 text-sm"
              />
              <p className="text-xs text-gray-500">
                A whole number from {MIN_HOURS} to {MAX_HOURS} (one week).
              </p>
            </div>

            {formError && (
              <p className="rounded bg-red-50 p-3 text-sm text-red-700">{formError}</p>
            )}
            {notice && <p className="rounded bg-green-50 p-3 text-sm text-green-800">{notice}</p>}

            <button
              type="submit"
              disabled={saving || unchanged}
              className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save"}
            </button>
          </form>
        )}
      </section>
    </div>
  );
}