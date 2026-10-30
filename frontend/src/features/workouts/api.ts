import { apiFetch } from "../../api/client";
import type { Workout, WorkoutEstimate, WorkoutFilters, WorkoutItem, WorkoutSummary, WorkoutWrite } from "./types";

export function listWorkouts(filters: WorkoutFilters): Promise<WorkoutSummary[]> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  const query = params.toString();
  return apiFetch<WorkoutSummary[]>(query ? `/workouts?${query}` : "/workouts");
}

export function getWorkout(workoutId: string): Promise<Workout> {
  return apiFetch<Workout>(`/workouts/${workoutId}`);
}

export function createWorkout(payload: WorkoutWrite): Promise<Workout> {
  return apiFetch<Workout>("/workouts", { method: "POST", body: JSON.stringify(payload) });
}

export function updateWorkout(workoutId: string, payload: Partial<WorkoutWrite>): Promise<Workout> {
  return apiFetch<Workout>(`/workouts/${workoutId}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function deleteWorkout(workoutId: string): Promise<void> {
  return apiFetch<void>(`/workouts/${workoutId}`, { method: "DELETE" });
}

export function duplicateWorkout(workoutId: string): Promise<Workout> {
  return apiFetch<Workout>(`/workouts/${workoutId}/duplicate`, { method: "POST" });
}

/** Duration, TSS and profile of steps being edited; stores nothing. */
export function estimateWorkout(steps: WorkoutItem[], ftpW: number | null): Promise<WorkoutEstimate> {
  return apiFetch<WorkoutEstimate>("/workouts/estimate", { method: "POST", body: JSON.stringify({ steps, ftp_w: ftpW }) });
}
