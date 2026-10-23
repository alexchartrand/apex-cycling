import { apiFetch } from "../../api/client";
import type { Insight } from "./types";

export function listInsights(athleteId: string, days: number, limit: number): Promise<Insight[]> {
  return apiFetch<Insight[]>(`/athletes/${athleteId}/insights?days=${days}&limit=${limit}`);
}

export function listSessionInsights(athleteId: string, eventId: string): Promise<Insight[]> {
  return apiFetch<Insight[]>(`/athletes/${athleteId}/sessions/${encodeURIComponent(eventId)}/insights`);
}
