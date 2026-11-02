import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createPlannedSession,
  deletePlannedSession,
  getPlanComparison,
  linkPlanActivity,
  linkPlannedSession,
  listPlannedSessions,
  unlinkPlanActivity,
  unlinkPlannedSession,
  updatePlannedSession,
} from "./api";
import type { PlannedSessionUpdate, PlannedSessionWrite } from "./types";

export function usePlannedSessions(athleteId: string) {
  return useQuery({ queryKey: ["planned-sessions", athleteId], queryFn: () => listPlannedSessions(athleteId), enabled: athleteId !== "" });
}

function useInvalidatePlan(athleteId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["planned-sessions", athleteId] });
}

export function useSavePlan(athleteId: string) {
  const invalidate = useInvalidatePlan(athleteId);
  return useMutation({
    mutationFn: ({ planId, payload }: { planId?: string; payload: PlannedSessionWrite | PlannedSessionUpdate }) =>
      planId ? updatePlannedSession(athleteId, planId, payload) : createPlannedSession(athleteId, payload as PlannedSessionWrite),
    onSuccess: invalidate,
  });
}

export function useDeletePlan(athleteId: string) {
  const invalidate = useInvalidatePlan(athleteId);
  return useMutation({ mutationFn: (planId: string) => deletePlannedSession(athleteId, planId), onSuccess: invalidate });
}

export type PlanAnswer = { planId: string } & (
  | { status: "planned" | "done" | "skipped" }
  | { link: string }
  | { unlink: true }
  | { linkActivity: string }
  | { unlinkActivity: true }
);

/** Done, skipped or planned again, or a link to the session or recording ridden (done) / its removal
 * (planned again once nothing is linked). */
export function usePlanAnswer(athleteId: string) {
  const invalidate = useInvalidatePlan(athleteId);
  return useMutation({
    mutationFn: (args: PlanAnswer) => {
      if ("link" in args) return linkPlannedSession(athleteId, args.planId, args.link);
      if ("unlink" in args) return unlinkPlannedSession(athleteId, args.planId);
      if ("linkActivity" in args) return linkPlanActivity(athleteId, args.planId, args.linkActivity);
      if ("unlinkActivity" in args) return unlinkPlanActivity(athleteId, args.planId);
      return updatePlannedSession(athleteId, args.planId, { status: args.status });
    },
    onSuccess: invalidate,
  });
}

/** The plan against the session and/or recording linked to it; only asked for once linked. */
export function usePlanComparison(athleteId: string, planId: string, linked: boolean) {
  return useQuery({
    queryKey: ["planned-sessions", athleteId, planId, "comparison"],
    queryFn: () => getPlanComparison(athleteId, planId),
    enabled: athleteId !== "" && linked,
  });
}
