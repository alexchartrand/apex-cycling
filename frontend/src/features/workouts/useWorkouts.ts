import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useActiveAthlete } from "../athletes/useActiveAthlete";
import { useCurrentMetrics } from "../athletes/useAthlete";
import { createWorkout, deleteWorkout, duplicateWorkout, estimateWorkout, getWorkout, listWorkouts, updateWorkout } from "./api";
import type { Workout, WorkoutFilters, WorkoutItem, WorkoutWrite } from "./types";

export function useWorkouts(filters: WorkoutFilters) {
  return useQuery({ queryKey: ["workouts", filters], queryFn: () => listWorkouts(filters), placeholderData: keepPreviousData });
}

export function useWorkout(workoutId: string | undefined) {
  return useQuery({ queryKey: ["workout", workoutId], queryFn: () => getWorkout(workoutId!), enabled: workoutId != null });
}

/** A saved workout goes into its own cache entry and the lists refetch. */
function useStoreWorkout() {
  const queryClient = useQueryClient();
  return (workout: Workout) => {
    queryClient.setQueryData(["workout", workout.id], workout);
    return queryClient.invalidateQueries({ queryKey: ["workouts"] });
  };
}

export function useSaveWorkout() {
  const store = useStoreWorkout();
  return useMutation({
    mutationFn: ({ workoutId, payload }: { workoutId?: string; payload: WorkoutWrite }) =>
      workoutId ? updateWorkout(workoutId, payload) : createWorkout(payload),
    onSuccess: store,
  });
}

export function useDuplicateWorkout() {
  const store = useStoreWorkout();
  return useMutation({ mutationFn: duplicateWorkout, onSuccess: store });
}

export function useDeleteWorkout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteWorkout,
    onSuccess: (_, workoutId) => {
      queryClient.removeQueries({ queryKey: ["workout", workoutId] });
      return queryClient.invalidateQueries({ queryKey: ["workouts"] });
    },
  });
}

/** The live chart: steps are null while the editor holds something the server would refuse. */
export function useWorkoutEstimate(steps: WorkoutItem[] | null, ftpW: number | null) {
  return useQuery({
    queryKey: ["workout-estimate", steps, ftpW],
    queryFn: () => estimateWorkout(steps!, ftpW),
    enabled: steps != null && steps.length > 0,
    placeholderData: keepPreviousData,
    staleTime: Infinity,
  });
}

/** Today's FTP of the athlete on screen, so watt targets get an intensity; null without one. */
export function useEstimateFtp(): number | null {
  const athlete = useActiveAthlete();
  const metrics = useCurrentMetrics(athlete.data?.id ?? "");
  return metrics.data?.ftp_w?.value ?? null;
}
