import { apiFetch } from "../../api/client";
import type { PlanComparison, PlannedSession, PlannedSessionUpdate, PlannedSessionWrite } from "./types";

const base = (athleteId: string) => `/athletes/${athleteId}/planned-sessions`;

export function listPlannedSessions(athleteId: string): Promise<PlannedSession[]> {
  return apiFetch<PlannedSession[]>(base(athleteId));
}

export function createPlannedSession(athleteId: string, payload: PlannedSessionWrite): Promise<PlannedSession> {
  return apiFetch<PlannedSession>(base(athleteId), { method: "POST", body: JSON.stringify(payload) });
}

export function updatePlannedSession(athleteId: string, planId: string, payload: PlannedSessionUpdate): Promise<PlannedSession> {
  return apiFetch<PlannedSession>(`${base(athleteId)}/${planId}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function deletePlannedSession(athleteId: string, planId: string): Promise<void> {
  return apiFetch<void>(`${base(athleteId)}/${planId}`, { method: "DELETE" });
}

export function linkPlannedSession(athleteId: string, planId: string, externalEventId: string): Promise<PlannedSession> {
  return apiFetch<PlannedSession>(`${base(athleteId)}/${planId}/session`, {
    method: "PUT",
    body: JSON.stringify({ external_event_id: externalEventId }),
  });
}

export function unlinkPlannedSession(athleteId: string, planId: string): Promise<PlannedSession> {
  return apiFetch<PlannedSession>(`${base(athleteId)}/${planId}/session`, { method: "DELETE" });
}

export function getPlanComparison(athleteId: string, planId: string): Promise<PlanComparison> {
  return apiFetch<PlanComparison>(`${base(athleteId)}/${planId}/comparison`);
}
