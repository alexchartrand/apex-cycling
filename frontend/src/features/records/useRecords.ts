import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createManualResult, deleteManualResult, listManualResults, listRecordHistory, listRecords, updateManualResult } from "./api";
import type { ManualResultPayload, RecordSelection } from "./types";

/** The athlete's records board (best per place, event and start type). */
export function useRecords(athleteId: string) {
  return useQuery({
    queryKey: ["records", athleteId],
    queryFn: () => listRecords(athleteId),
    enabled: athleteId !== "",
  });
}

export function useRecordHistory(athleteId: string, selection: RecordSelection | null) {
  return useQuery({
    queryKey: ["records", athleteId, "history", selection],
    queryFn: () => listRecordHistory(athleteId, selection!),
    enabled: athleteId !== "" && selection !== null,
  });
}

export function useManualResults(athleteId: string) {
  return useQuery({
    queryKey: ["manual-results", athleteId],
    queryFn: () => listManualResults(athleteId),
    enabled: athleteId !== "",
  });
}

/** Add, edit or delete a manual result; the board and history include them, so they refetch too. */
function useManualResultMutation<T>(mutationFn: (variables: T) => Promise<unknown>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () =>
      Promise.all(["records", "manual-results"].map((key) => queryClient.invalidateQueries({ queryKey: [key] }))),
  });
}

export function useCreateManualResult(athleteId: string) {
  return useManualResultMutation((payload: ManualResultPayload) => createManualResult(athleteId, payload));
}

export function useUpdateManualResult(athleteId: string) {
  return useManualResultMutation(({ id, payload }: { id: string; payload: ManualResultPayload }) =>
    updateManualResult(athleteId, id, payload),
  );
}

export function useDeleteManualResult(athleteId: string) {
  return useManualResultMutation((id: string) => deleteManualResult(athleteId, id));
}
