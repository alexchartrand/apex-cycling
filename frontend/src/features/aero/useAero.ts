import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createAeroTest, deleteAeroTest, estimateAero, listAeroTests, updateAeroTest } from "./api";
import type { AeroEstimateRequest, AeroTestCreate, AeroTestUpdate } from "./types";

/** A POST that only computes, so it is cached like a read; the previous answer stays up while inputs change. */
export function useAeroEstimate(athleteId: string, eventId: string, request: AeroEstimateRequest) {
  return useQuery({
    queryKey: ["aero-estimate", athleteId, eventId, request],
    queryFn: () => estimateAero(athleteId, eventId, request),
    enabled: athleteId !== "" && eventId !== "",
    placeholderData: keepPreviousData,
  });
}

export function useAeroTests(athleteId: string) {
  return useQuery({
    queryKey: ["aero-tests", athleteId],
    queryFn: () => listAeroTests(athleteId),
    enabled: athleteId !== "",
  });
}

function useInvalidateTests(athleteId: string) {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: ["aero-tests", athleteId] });
  };
}

export function useCreateAeroTest(athleteId: string) {
  const invalidate = useInvalidateTests(athleteId);
  return useMutation({
    mutationFn: (payload: AeroTestCreate) => createAeroTest(athleteId, payload),
    onSuccess: invalidate,
  });
}

export function useUpdateAeroTest(athleteId: string) {
  const invalidate = useInvalidateTests(athleteId);
  return useMutation({
    mutationFn: ({ testId, payload }: { testId: string; payload: AeroTestUpdate }) => updateAeroTest(athleteId, testId, payload),
    onSuccess: invalidate,
  });
}

export function useDeleteAeroTest(athleteId: string) {
  const invalidate = useInvalidateTests(athleteId);
  return useMutation({
    mutationFn: (testId: string) => deleteAeroTest(athleteId, testId),
    onSuccess: invalidate,
  });
}
