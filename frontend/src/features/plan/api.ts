import { apiFetch } from "../../api/client";
import { downloadFile } from "../../api/download";
import type { ExportFormat } from "../workouts/types";
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

export function linkPlanActivity(athleteId: string, planId: string, activityId: string): Promise<PlannedSession> {
  return apiFetch<PlannedSession>(`${base(athleteId)}/${planId}/activity`, {
    method: "PUT",
    body: JSON.stringify({ activity_id: activityId }),
  });
}

export function unlinkPlanActivity(athleteId: string, planId: string): Promise<PlannedSession> {
  return apiFetch<PlannedSession>(`${base(athleteId)}/${planId}/activity`, { method: "DELETE" });
}

export function getPlanComparison(athleteId: string, planId: string): Promise<PlanComparison> {
  return apiFetch<PlanComparison>(`${base(athleteId)}/${planId}/comparison`);
}

/** The plan's workout as a file, with the FTP in force on the planned date. */
export function downloadPlanWorkout(athleteId: string, planId: string, format: ExportFormat): Promise<void> {
  return downloadFile(`${base(athleteId)}/${planId}/export/${format}`, `workout.${format}`);
}
