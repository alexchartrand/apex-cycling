import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { importTransponderAssignmentNow, listTransponderAssignments, reportTransponderUsage } from "./api";
import type { ReportUsagePayload } from "./types";

function assignmentsKey(athleteId: string) {
  return ["transponder-assignments", athleteId];
}

export function useTransponderAssignments(athleteId: string) {
  return useQuery({
    queryKey: assignmentsKey(athleteId),
    queryFn: () => listTransponderAssignments(athleteId),
  });
}

export function useReportTransponderUsage(athleteId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ReportUsagePayload) => reportTransponderUsage(athleteId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: assignmentsKey(athleteId) }),
  });
}

export function useImportTransponderAssignmentNow(athleteId: string) {
  return useMutation({
    mutationFn: (assignmentId: string) => importTransponderAssignmentNow(athleteId, assignmentId),
  });
}
