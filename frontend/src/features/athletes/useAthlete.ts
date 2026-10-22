import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteMetric, fetchAthlete, fetchCurrentMetrics, fetchMyAthlete, listMetrics, recordMetrics, setLeaderboardConsent, updateAthlete } from "./api";
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

/** Any athlete I have access to (a coached athlete, a managed one). */
export function useAthlete(athleteId: string) {
  return useQuery({
    queryKey: ["athletes", athleteId],
    queryFn: () => fetchAthlete(athleteId),
    enabled: athleteId !== "",
  });
}

function useCacheUpdatedAthlete() {
  const queryClient = useQueryClient();
  return (athlete: Athlete) => {
    queryClient.setQueryData(["athletes", athlete.id], athlete);
    if (queryClient.getQueryData<Athlete>(MY_ATHLETE_KEY)?.id === athlete.id) {
      queryClient.setQueryData(MY_ATHLETE_KEY, athlete);
    }
  };
}

export function useUpdateAthlete(athleteId: string) {
  const cache = useCacheUpdatedAthlete();
  return useMutation({
    mutationFn: (payload: AthleteUpdate) => updateAthlete(athleteId, payload),
    onSuccess: cache,
  });
}

/** Appear on (or leave) one club's leaderboard. */
export function useSetLeaderboardConsent(athleteId: string) {
  const cache = useCacheUpdatedAthlete();
  return useMutation({
    mutationFn: ({ clubId, optIn }: { clubId: string; optIn: boolean }) => setLeaderboardConsent(athleteId, clubId, optIn),
    onSuccess: cache,
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
