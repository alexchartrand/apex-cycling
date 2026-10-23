import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import {
  importTransponderAssignmentNow,
  listIngestionRuns,
  listTransponderAssignments,
  reportTransponderUsage,
  stopTransponderAssignment,
} from "./api";
import type { ReportUsagePayload } from "./types";

function assignmentsKey(athleteId: string) {
  return ["transponder-assignments", athleteId];
}

function ingestionRunsKey(athleteId: string) {
  return ["ingestion-runs", athleteId];
}

/** A sync can add sessions, laps and records, so whatever shows them refetches (queries stay fresh for 60 s). */
function invalidateTrainingData(queryClient: QueryClient, athleteId: string) {
  return Promise.all(
    [ingestionRunsKey(athleteId), ["sessions", athleteId], ["session-detail", athleteId], ["records", athleteId], ["tracks", athleteId], ["insights", athleteId]].map(
      (queryKey) => queryClient.invalidateQueries({ queryKey }),
    ),
  );
}

export function useTransponderAssignments(athleteId: string) {
  return useQuery({
    queryKey: assignmentsKey(athleteId),
    queryFn: () => listTransponderAssignments(athleteId),
    enabled: athleteId.length > 0,
  });
}

export function useReportTransponderUsage(athleteId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ReportUsagePayload) => reportTransponderUsage(athleteId, payload),
    // Adding a transponder runs its first sync straight away.
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: assignmentsKey(athleteId) });
      return invalidateTrainingData(queryClient, athleteId);
    },
  });
}

export function useImportTransponderAssignmentNow(athleteId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assignmentId: string) => importTransponderAssignmentNow(athleteId, assignmentId),
    onSuccess: () => invalidateTrainingData(queryClient, athleteId),
  });
}

export function useStopTransponderAssignment(athleteId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assignmentId: string) => stopTransponderAssignment(athleteId, assignmentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: assignmentsKey(athleteId) }),
  });
}

export function useIngestionRuns(athleteId: string) {
  return useQuery({
    queryKey: ingestionRunsKey(athleteId),
    queryFn: () => listIngestionRuns(athleteId),
    enabled: athleteId.length > 0,
  });
}
