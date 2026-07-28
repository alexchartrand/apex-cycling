import { apiFetch } from "../../api/client";
import type { IngestionRun, IngestionRunWithSource, ReportUsagePayload, TransponderAssignment } from "./types";

export function listTransponderAssignments(athleteId: string): Promise<TransponderAssignment[]> {
  return apiFetch<TransponderAssignment[]>(`/athletes/${athleteId}/transponder-assignments`);
}

export function reportTransponderUsage(
  athleteId: string,
  payload: ReportUsagePayload,
): Promise<TransponderAssignment> {
  return apiFetch<TransponderAssignment>(`/athletes/${athleteId}/transponder-assignments`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function importTransponderAssignmentNow(
  athleteId: string,
  assignmentId: string,
): Promise<IngestionRun> {
  return apiFetch<IngestionRun>(`/athletes/${athleteId}/transponder-assignments/${assignmentId}/import`, {
    method: "POST",
  });
}

export function listIngestionRuns(athleteId: string): Promise<IngestionRunWithSource[]> {
  return apiFetch<IngestionRunWithSource[]>(`/athletes/${athleteId}/ingestion-runs`);
}

export function stopTransponderAssignment(
  athleteId: string,
  assignmentId: string,
): Promise<TransponderAssignment> {
  return apiFetch<TransponderAssignment>(
    `/athletes/${athleteId}/transponder-assignments/${assignmentId}/stop`,
    { method: "POST" },
  );
}
