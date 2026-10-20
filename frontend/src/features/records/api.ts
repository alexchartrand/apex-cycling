import { apiFetch } from "../../api/client";
import type { ManualResult, ManualResultPayload, RecordEntry, RecordSelection } from "./types";

export function listRecords(athleteId: string): Promise<RecordEntry[]> {
  return apiFetch<RecordEntry[]>(`/athletes/${athleteId}/records`);
}

export function listRecordHistory(athleteId: string, selection: RecordSelection): Promise<RecordEntry[]> {
  const query = new URLSearchParams({ event_key: selection.event_key, start_type: selection.start_type });
  // A manual result with no track is identified by its venue text.
  if (selection.track_id) query.set("track_id", selection.track_id);
  else query.set("venue", selection.place);
  return apiFetch<RecordEntry[]>(`/athletes/${athleteId}/records/history?${query.toString()}`);
}

export function listManualResults(athleteId: string): Promise<ManualResult[]> {
  return apiFetch<ManualResult[]>(`/athletes/${athleteId}/manual-results`);
}

export function createManualResult(athleteId: string, payload: ManualResultPayload): Promise<ManualResult> {
  return apiFetch<ManualResult>(`/athletes/${athleteId}/manual-results`, { method: "POST", body: JSON.stringify(payload) });
}

export function updateManualResult(athleteId: string, id: string, payload: ManualResultPayload): Promise<ManualResult> {
  return apiFetch<ManualResult>(`/athletes/${athleteId}/manual-results/${id}`, { method: "PUT", body: JSON.stringify(payload) });
}

export function deleteManualResult(athleteId: string, id: string): Promise<void> {
  return apiFetch<void>(`/athletes/${athleteId}/manual-results/${id}`, { method: "DELETE" });
}
