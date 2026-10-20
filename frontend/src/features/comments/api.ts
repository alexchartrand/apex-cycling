import { apiFetch } from "../../api/client";
import type { SessionComment } from "./types";

const base = (athleteId: string, eventId: string) => `/athletes/${athleteId}/sessions/${encodeURIComponent(eventId)}/comments`;

export function listComments(athleteId: string, eventId: string): Promise<SessionComment[]> {
  return apiFetch<SessionComment[]>(base(athleteId, eventId));
}

export function addComment(athleteId: string, eventId: string, body: string): Promise<SessionComment> {
  return apiFetch<SessionComment>(base(athleteId, eventId), { method: "POST", body: JSON.stringify({ body }) });
}

export function editComment(athleteId: string, eventId: string, commentId: string, body: string): Promise<SessionComment> {
  return apiFetch<SessionComment>(`${base(athleteId, eventId)}/${commentId}`, { method: "PATCH", body: JSON.stringify({ body }) });
}

export function deleteComment(athleteId: string, eventId: string, commentId: string): Promise<void> {
  return apiFetch<void>(`${base(athleteId, eventId)}/${commentId}`, { method: "DELETE" });
}

/** Called when the thread is shown, so the inbox forgets what came before. */
export function markThreadRead(athleteId: string, eventId: string): Promise<void> {
  return apiFetch<void>(`${base(athleteId, eventId)}/read`, { method: "POST" });
}
