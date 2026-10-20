import { apiFetch } from "../../api/client";
import type {
  ProgressionParams,
  ProgressionPoint,
  SessionDetail,
  SessionSummary,
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
