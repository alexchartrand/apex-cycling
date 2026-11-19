import { apiFetch } from "../../api/client";
import type { PlannedSession } from "../plan/types";
import type { Phase, TrainingPlan, TrainingPlanWrite } from "./types";

const base = (athleteId: string) => `/athletes/${athleteId}/training-plans`;

export function listTrainingPlans(athleteId: string): Promise<TrainingPlan[]> {
  return apiFetch<TrainingPlan[]>(base(athleteId));
}

export function getTrainingPlan(athleteId: string, planId: string): Promise<TrainingPlan> {
  return apiFetch<TrainingPlan>(`${base(athleteId)}/${planId}`);
}

export function createTrainingPlan(athleteId: string, payload: TrainingPlanWrite): Promise<TrainingPlan> {
  return apiFetch<TrainingPlan>(base(athleteId), { method: "POST", body: JSON.stringify(payload) });
}

export function updateTrainingPlan(athleteId: string, planId: string, payload: Partial<TrainingPlanWrite>): Promise<TrainingPlan> {
  return apiFetch<TrainingPlan>(`${base(athleteId)}/${planId}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function deleteTrainingPlan(athleteId: string, planId: string): Promise<void> {
  return apiFetch<void>(`${base(athleteId)}/${planId}`, { method: "DELETE" });
}

export function suggestPhases(
  athleteId: string,
  payload: { start_date: string; end_date: string; race_priority: "A" | "B" | "C" | null },
): Promise<Phase[]> {
  return apiFetch<Phase[]>(`${base(athleteId)}/suggest-phases`, { method: "POST", body: JSON.stringify(payload) });
}

/** The planned sessions of one plan. */
export function listPlanSessions(athleteId: string, planId: string): Promise<PlannedSession[]> {
  return apiFetch<PlannedSession[]>(`/athletes/${athleteId}/planned-sessions?training_plan_id=${encodeURIComponent(planId)}`);
}
