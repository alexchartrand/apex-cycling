import { apiFetch } from "../../api/client";
import type { RecordEntry } from "./types";

export function listRecords(athleteId: string): Promise<RecordEntry[]> {
  return apiFetch<RecordEntry[]>(`/athletes/${athleteId}/records`);
}
