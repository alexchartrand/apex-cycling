import { apiFetch } from "../../api/client";
import type { Goal, GoalCreate, GoalUpdate } from "./types";

const base = (athleteId: string) => `/athletes/${athleteId}/goals`;

export function listGoals(athleteId: string): Promise<Goal[]> {
  return apiFetch<Goal[]>(base(athleteId));
}

export function createGoal(athleteId: string, payload: GoalCreate): Promise<Goal> {
  return apiFetch<Goal>(base(athleteId), { method: "POST", body: JSON.stringify(payload) });
}

export function updateGoal(athleteId: string, goalId: string, payload: GoalUpdate): Promise<Goal> {
  return apiFetch<Goal>(`${base(athleteId)}/${goalId}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function deleteGoal(athleteId: string, goalId: string): Promise<void> {
  return apiFetch<void>(`${base(athleteId)}/${goalId}`, { method: "DELETE" });
}
