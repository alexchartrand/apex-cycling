import { apiFetch } from "../../api/client";
import type { AthleteCard, CoachLink, CoachLinkRequest, CommentInboxItem } from "./types";

export function listCoachedAthletes(): Promise<CoachLink[]> {
  return apiFetch<CoachLink[]>("/coach-links/athletes");
}

export function listMyCoaches(athleteId?: string): Promise<CoachLink[]> {
  return apiFetch<CoachLink[]>(`/coach-links/coaches${athleteId ? `?athlete_id=${athleteId}` : ""}`);
}

export function listCoachInbox(): Promise<CoachLink[]> {
  return apiFetch<CoachLink[]>("/coach-links/inbox");
}

export function fetchDashboard(): Promise<AthleteCard[]> {
  return apiFetch<AthleteCard[]>("/coach-links/dashboard");
}

export function requestCoachLink(payload: CoachLinkRequest): Promise<{ requested: boolean }> {
  return apiFetch("/coach-links", { method: "POST", body: JSON.stringify(payload) });
}

export function acceptCoachLink(linkId: string): Promise<CoachLink> {
  return apiFetch<CoachLink>(`/coach-links/${linkId}/accept`, { method: "POST" });
}

/** Revokes an active link, or declines / cancels a pending one. */
export function revokeCoachLink(linkId: string): Promise<void> {
  return apiFetch<void>(`/coach-links/${linkId}/revoke`, { method: "POST" });
}

export function listCommentInbox(): Promise<CommentInboxItem[]> {
  return apiFetch<CommentInboxItem[]>("/comments/inbox");
}
