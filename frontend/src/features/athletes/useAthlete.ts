import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteMetric, fetchCurrentMetrics, fetchMyAthlete, listMetrics, recordMetrics, updateAthlete } from "./api";
import type { Athlete, AthleteMetricPayload, AthleteUpdate } from "./types";

const MY_ATHLETE_KEY = ["athletes", "me"];

function metricsKey(athleteId: string) {
  return ["athlete-metrics", athleteId];
}

export function useMyAthlete() {
  return useQuery({
    queryKey: MY_ATHLETE_KEY,
    queryFn: fetchMyAthlete,
  });
}

export function useUpdateAthlete(athleteId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AthleteUpdate) => updateAthlete(athleteId, payload),
    onSuccess: (athlete) => {
      if (queryClient.getQueryData<Athlete>(MY_ATHLETE_KEY)?.id === athlete.id) {
        queryClient.setQueryData(MY_ATHLETE_KEY, athlete);
      }
    },
  });
}

export function useMetricsHistory(athleteId: string) {
  return useQuery({
    queryKey: [...metricsKey(athleteId), "history"],
    queryFn: () => listMetrics(athleteId),
    enabled: athleteId.length > 0,
  });
}

export function useCurrentMetrics(athleteId: string) {
  return useQuery({
    queryKey: [...metricsKey(athleteId), "current"],
    queryFn: () => fetchCurrentMetrics(athleteId),
    enabled: athleteId.length > 0,
  });
}

export function useRecordMetrics(athleteId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AthleteMetricPayload) => recordMetrics(athleteId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: metricsKey(athleteId) }),
  });
}

export function useDeleteMetric(athleteId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (metricId: string) => deleteMetric(athleteId, metricId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: metricsKey(athleteId) }),
  });
}
