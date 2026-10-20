import { apiFetch } from "../../api/client";
import type {
  Effort,
  LapUpdate,
  ProgressionParams,
  ProgressionPoint,
  SessionDetail,
  SessionMeta,
  SessionSummary,
  SessionUpdate,
  TrackSummary,
  TrackUpdate,
} from "./types";

export function listSessions(athleteId: string): Promise<SessionSummary[]> {
  return apiFetch<SessionSummary[]>(`/athletes/${athleteId}/sessions`);
}

export function listTracks(athleteId: string): Promise<TrackSummary[]> {
  return apiFetch<TrackSummary[]>(`/athletes/${athleteId}/tracks`);
}

export function getSessionDetail(athleteId: string, eventId: string): Promise<SessionDetail> {
  return apiFetch<SessionDetail>(`/athletes/${athleteId}/sessions/${eventId}`);
}

export function getProgression(athleteId: string, params: ProgressionParams): Promise<ProgressionPoint[]> {
  const query = new URLSearchParams();
  query.set("metric", params.metric);
  if (params.track_id) query.set("track_id", params.track_id);
  if (params.track_view_id) query.set("track_view_id", params.track_view_id);
  if (params.distance_m != null) query.set("distance_m", String(params.distance_m));
  if (params.from) query.set("from", params.from);
  if (params.to) query.set("to", params.to);
  return apiFetch<ProgressionPoint[]>(`/athletes/${athleteId}/progression?${query.toString()}`);
}

export function updateTrack(trackId: string, payload: TrackUpdate): Promise<TrackSummary> {
  return apiFetch<TrackSummary>(`/tracks/${trackId}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function listEfforts(athleteId: string, eventId: string): Promise<Effort[]> {
  return apiFetch<Effort[]>(`/athletes/${athleteId}/sessions/${eventId}/efforts`);
}

export function updateSession(athleteId: string, eventId: string, payload: SessionUpdate): Promise<SessionMeta> {
  return apiFetch<SessionMeta>(`/athletes/${athleteId}/sessions/${eventId}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function updateLap(athleteId: string, lapId: string, payload: LapUpdate): Promise<unknown> {
  return apiFetch(`/athletes/${athleteId}/laps/${lapId}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function labelEffort(athleteId: string, eventId: string, firstLapId: string, label: string | null): Promise<unknown> {
  return apiFetch(`/athletes/${athleteId}/sessions/${eventId}/efforts/${firstLapId}/label`, {
    method: "PUT",
    body: JSON.stringify({ label }),
  });
}
