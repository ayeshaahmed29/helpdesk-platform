import { apiFetch } from "./client";

export type SlaSettings = {
  first_reply_hours: number;
};

export function getSlaSettings(): Promise<SlaSettings> {
  return apiFetch<SlaSettings>("/settings/sla");
}

export function updateSlaSettings(firstReplyHours: number): Promise<SlaSettings> {
  return apiFetch<SlaSettings>("/settings/sla", {
    method: "PUT",
    body: JSON.stringify({ first_reply_hours: firstReplyHours }),
  });
}