import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: assignmentsKey(athleteId) });
      queryClient.invalidateQueries({ queryKey: ingestionRunsKey(athleteId) });
    },
  });
}

export function useImportTransponderAssignmentNow(athleteId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assignmentId: string) => importTransponderAssignmentNow(athleteId, assignmentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ingestionRunsKey(athleteId) }),
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
