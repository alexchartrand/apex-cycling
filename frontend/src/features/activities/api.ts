import { apiFetch } from "../../api/client";
import type {
  Activity,
  ActivityAnalysis,
  ActivityStreams,
  ActivityUpdate,
  IntervalsStatus,
  PowerCurvePoint,
  PowerProfile,
  SessionSuggestion,
  StravaStatus,
  TrainingLoad,
  UploadResult,
} from "./types";

const base = (athleteId: string) => `/athletes/${athleteId}`;

export function listActivities(
  athleteId: string,
  params: { start?: string; end?: string; limit?: number; offset?: number } = {},
): Promise<Activity[]> {
  const query = new URLSearchParams();
  if (params.start) query.set("start", params.start);
  if (params.end) query.set("end", params.end);
  query.set("limit", String(params.limit ?? 200));
  if (params.offset) query.set("offset", String(params.offset));
  return apiFetch<Activity[]>(`${base(athleteId)}/activities?${query.toString()}`);
}

export function getActivity(athleteId: string, activityId: string): Promise<Activity> {
  return apiFetch<Activity>(`${base(athleteId)}/activities/${activityId}`);
}

export function updateActivity(athleteId: string, activityId: string, payload: ActivityUpdate): Promise<Activity> {
  return apiFetch<Activity>(`${base(athleteId)}/activities/${activityId}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function deleteActivity(athleteId: string, activityId: string): Promise<void> {
  return apiFetch<void>(`${base(athleteId)}/activities/${activityId}`, { method: "DELETE" });
}

/** One file per request, so the screen can show each file's own progress. */
export async function uploadActivityFile(athleteId: string, file: File): Promise<UploadResult> {
  const form = new FormData();
  form.append("files", file);
  const [result] = await apiFetch<UploadResult[]>(`${base(athleteId)}/activities/upload`, { method: "POST", body: form });
  return result;
}

export function getActivityStreams(athleteId: string, activityId: string, maxPoints = 1200): Promise<ActivityStreams> {
  return apiFetch<ActivityStreams>(`${base(athleteId)}/activities/${activityId}/streams?max_points=${maxPoints}`);
}

export function getActivityAnalysis(athleteId: string, activityId: string): Promise<ActivityAnalysis> {
  return apiFetch<ActivityAnalysis>(`${base(athleteId)}/activities/${activityId}/analysis`);
}

export function getSessionSuggestion(athleteId: string, activityId: string): Promise<SessionSuggestion> {
  return apiFetch<SessionSuggestion>(`${base(athleteId)}/activities/${activityId}/session/suggestion`);
}

export function linkActivitySession(
  athleteId: string,
  activityId: string,
  payload: { external_event_id: string; clock_offset_s?: number | null },
): Promise<Activity> {
  return apiFetch<Activity>(`${base(athleteId)}/activities/${activityId}/session`, { method: "PUT", body: JSON.stringify(payload) });
}

export function unlinkActivitySession(athleteId: string, activityId: string): Promise<Activity> {
  return apiFetch<Activity>(`${base(athleteId)}/activities/${activityId}/session`, { method: "DELETE" });
}

export function getTrainingLoad(athleteId: string, days: number): Promise<TrainingLoad> {
  return apiFetch<TrainingLoad>(`${base(athleteId)}/training-load?days=${days}`);
}

export function getPowerCurve(athleteId: string, range: { start?: string; end?: string } = {}): Promise<PowerCurvePoint[]> {
  const query = new URLSearchParams();
  if (range.start) query.set("start", range.start);
  if (range.end) query.set("end", range.end);
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return apiFetch<PowerCurvePoint[]>(`${base(athleteId)}/power-curve${suffix}`);
}

export function getPowerProfile(athleteId: string, days: number): Promise<PowerProfile> {
  return apiFetch<PowerProfile>(`${base(athleteId)}/power-profile?days=${days}`);
}

// --- Intervals.icu -----------------------------------------------------------------

export function getIntervalsStatus(athleteId: string): Promise<IntervalsStatus> {
  return apiFetch<IntervalsStatus>(`${base(athleteId)}/intervals`);
}

export function connectIntervals(athleteId: string, apiKey: string): Promise<IntervalsStatus> {
  return apiFetch<IntervalsStatus>(`${base(athleteId)}/intervals`, { method: "PUT", body: JSON.stringify({ api_key: apiKey }) });
}

export function syncIntervals(athleteId: string): Promise<IntervalsStatus> {
  return apiFetch<IntervalsStatus>(`${base(athleteId)}/intervals/sync`, { method: "POST" });
}

export function disconnectIntervals(athleteId: string): Promise<IntervalsStatus> {
  return apiFetch<IntervalsStatus>(`${base(athleteId)}/intervals`, { method: "DELETE" });
}

// --- Strava ----------------------------------------------------------------------------

export function getStravaStatus(athleteId: string): Promise<StravaStatus> {
  return apiFetch<StravaStatus>(`${base(athleteId)}/strava`);
}

export function getStravaAuthorizeUrl(athleteId: string): Promise<{ url: string }> {
  return apiFetch<{ url: string }>(`${base(athleteId)}/strava/authorize-url`);
}

export function syncStrava(athleteId: string): Promise<StravaStatus> {
  return apiFetch<StravaStatus>(`${base(athleteId)}/strava/sync`, { method: "POST" });
}

export function disconnectStrava(athleteId: string): Promise<StravaStatus> {
  return apiFetch<StravaStatus>(`${base(athleteId)}/strava`, { method: "DELETE" });
}
