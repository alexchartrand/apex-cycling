import { apiFetch } from "../../api/client";
import type { Athlete, AthleteMetric, AthleteMetricPayload, AthleteUpdate, CurrentMetrics } from "./types";

export function fetchMyAthlete(): Promise<Athlete> {
  return apiFetch<Athlete>("/athletes/me");
}

export function fetchAthlete(athleteId: string): Promise<Athlete> {
  return apiFetch<Athlete>(`/athletes/${athleteId}`);
}

export function updateAthlete(athleteId: string, payload: AthleteUpdate): Promise<Athlete> {
  return apiFetch<Athlete>(`/athletes/${athleteId}`, { method: "PATCH", body: JSON.stringify(payload) });
}

/** Only the athlete (or a club admin for a managed athlete) may change this. */
export function setLeaderboardConsent(athleteId: string, clubId: string, optIn: boolean): Promise<Athlete> {
  return apiFetch<Athlete>(`/athletes/${athleteId}/clubs/${clubId}/leaderboard`, {
    method: "PUT",
    body: JSON.stringify({ opt_in: optIn }),
  });
}

export function listMetrics(athleteId: string): Promise<AthleteMetric[]> {
  return apiFetch<AthleteMetric[]>(`/athletes/${athleteId}/metrics`);
}

export function fetchCurrentMetrics(athleteId: string): Promise<CurrentMetrics> {
  return apiFetch<CurrentMetrics>(`/athletes/${athleteId}/metrics/current`);
}

export function recordMetrics(athleteId: string, payload: AthleteMetricPayload): Promise<AthleteMetric> {
  return apiFetch<AthleteMetric>(`/athletes/${athleteId}/metrics`, { method: "POST", body: JSON.stringify(payload) });
}

export function deleteMetric(athleteId: string, metricId: string): Promise<void> {
  return apiFetch<void>(`/athletes/${athleteId}/metrics/${metricId}`, { method: "DELETE" });
}
