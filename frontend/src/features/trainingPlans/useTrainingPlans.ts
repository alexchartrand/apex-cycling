import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createTrainingPlan,
  deleteTrainingPlan,
  getTrainingPlan,
  listPlanSessions,
  listTrainingPlans,
  suggestPhases,
  updateTrainingPlan,
} from "./api";
import type { TrainingPlanWrite } from "./types";

const key = (athleteId: string, ...rest: unknown[]) => ["training-plans", athleteId, ...rest];

export function useTrainingPlans(athleteId: string) {
  return useQuery({ queryKey: key(athleteId), queryFn: () => listTrainingPlans(athleteId), enabled: athleteId !== "" });
}

export function useTrainingPlan(athleteId: string, planId: string | undefined) {
  return useQuery({
    queryKey: key(athleteId, "one", planId),
    queryFn: () => getTrainingPlan(athleteId, planId!),
    enabled: athleteId !== "" && !!planId,
  });
}

/** Under the planned-sessions key, so every plan change (dialog, AI accept) refreshes it. */
export function usePlanSessions(athleteId: string, planId: string | undefined) {
  return useQuery({
    queryKey: ["planned-sessions", athleteId, "training-plan", planId],
    queryFn: () => listPlanSessions(athleteId, planId!),
    enabled: athleteId !== "" && !!planId,
  });
}

function useInvalidate(athleteId: string) {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: key(athleteId) });
    queryClient.invalidateQueries({ queryKey: ["planned-sessions", athleteId] });
  };
}

export function useSaveTrainingPlan(athleteId: string) {
  const invalidate = useInvalidate(athleteId);
  return useMutation({
    mutationFn: ({ planId, payload }: { planId?: string; payload: TrainingPlanWrite }) =>
      planId ? updateTrainingPlan(athleteId, planId, payload) : createTrainingPlan(athleteId, payload),
    onSuccess: invalidate,
  });
}

export function useDeleteTrainingPlan(athleteId: string) {
  const invalidate = useInvalidate(athleteId);
  return useMutation({ mutationFn: (planId: string) => deleteTrainingPlan(athleteId, planId), onSuccess: invalidate });
}

export function useSuggestPhases(athleteId: string) {
  return useMutation({ mutationFn: (payload: Parameters<typeof suggestPhases>[1]) => suggestPhases(athleteId, payload) });
}
