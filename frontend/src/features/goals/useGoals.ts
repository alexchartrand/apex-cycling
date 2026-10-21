import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createGoal, deleteGoal, listGoals, updateGoal } from "./api";
import type { GoalCreate, GoalUpdate } from "./types";

export function useGoals(athleteId: string) {
  return useQuery({ queryKey: ["goals", athleteId], queryFn: () => listGoals(athleteId), enabled: athleteId !== "" });
}

function useInvalidateGoals(athleteId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["goals", athleteId] });
}

export function useSaveGoal(athleteId: string) {
  const invalidate = useInvalidateGoals(athleteId);
  return useMutation({
    mutationFn: ({ goalId, payload }: { goalId?: string; payload: GoalCreate | GoalUpdate }) =>
      goalId ? updateGoal(athleteId, goalId, payload) : createGoal(athleteId, payload as GoalCreate),
    onSuccess: invalidate,
  });
}

export function useDeleteGoal(athleteId: string) {
  const invalidate = useInvalidateGoals(athleteId);
  return useMutation({ mutationFn: (goalId: string) => deleteGoal(athleteId, goalId), onSuccess: invalidate });
}
