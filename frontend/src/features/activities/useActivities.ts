import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  connectIntervals,
  deleteActivity,
  disconnectIntervals,
  disconnectStrava,
  getActivity,
  getActivityAnalysis,
  getActivityStreams,
  getIntervalsStatus,
  getPowerCurve,
  getSessionSuggestion,
  getStravaAuthorizeUrl,
  getStravaStatus,
  getTrainingLoad,
  linkActivitySession,
  listActivities,
  syncIntervals,
  syncStrava,
  unlinkActivitySession,
  updateActivity,
  uploadActivityFile,
} from "./api";
import type { ActivityUpdate } from "./types";

export function useActivities(athleteId: string) {
  return useQuery({
    queryKey: ["activities", athleteId],
    queryFn: () => listActivities(athleteId),
    enabled: athleteId !== "",
  });
}

export function useActivity(athleteId: string, activityId: string) {
  return useQuery({
    queryKey: ["activity", athleteId, activityId],
    queryFn: () => getActivity(athleteId, activityId),
    enabled: athleteId !== "" && activityId !== "",
  });
}

export function useActivityStreams(athleteId: string, activityId: string) {
  return useQuery({
    queryKey: ["activity-streams", athleteId, activityId],
    queryFn: () => getActivityStreams(athleteId, activityId),
    enabled: athleteId !== "" && activityId !== "",
    staleTime: 5 * 60_000,
  });
}

export function useActivityAnalysis(athleteId: string, activityId: string) {
  return useQuery({
    queryKey: ["activity-analysis", athleteId, activityId],
    queryFn: () => getActivityAnalysis(athleteId, activityId),
    enabled: athleteId !== "" && activityId !== "",
  });
}

export function useSessionSuggestion(athleteId: string, activityId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["activity-suggestion", athleteId, activityId],
    queryFn: () => getSessionSuggestion(athleteId, activityId),
    enabled: enabled && athleteId !== "" && activityId !== "",
  });
}

export function useTrainingLoad(athleteId: string, days: number) {
  return useQuery({
    queryKey: ["training-load", athleteId, days],
    queryFn: () => getTrainingLoad(athleteId, days),
    enabled: athleteId !== "",
  });
}

export function usePowerCurve(athleteId: string, range: { start?: string; end?: string }, enabled = true) {
  return useQuery({
    queryKey: ["power-curve", athleteId, range],
    queryFn: () => getPowerCurve(athleteId, range),
    enabled: enabled && athleteId !== "",
  });
}

/** Everything derived from activities refetches when they change. */
function useInvalidateActivities() {
  const queryClient = useQueryClient();
  return () => {
    for (const key of ["activities", "activity", "activity-analysis", "activity-streams", "training-load", "power-curve", "session-detail", "session-efforts"]) {
      queryClient.invalidateQueries({ queryKey: [key] });
    }
  };
}

export function useUploadActivityFile(athleteId: string) {
  const invalidate = useInvalidateActivities();
  return useMutation({ mutationFn: (file: File) => uploadActivityFile(athleteId, file), onSuccess: invalidate });
}

export function useUpdateActivity(athleteId: string, activityId: string) {
  const invalidate = useInvalidateActivities();
  return useMutation({
    mutationFn: (payload: ActivityUpdate) => updateActivity(athleteId, activityId, payload),
    onSuccess: invalidate,
  });
}

export function useDeleteActivity(athleteId: string) {
  const invalidate = useInvalidateActivities();
  return useMutation({ mutationFn: (activityId: string) => deleteActivity(athleteId, activityId), onSuccess: invalidate });
}

// Linking moves the ride between its own page and the session's Ride tab, which
// redirect on `external_event_id`: the answer goes into the cache at once so
// neither page acts on the stale copy while the refetch runs.

export function useLinkActivitySession(athleteId: string, activityId: string) {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateActivities();
  return useMutation({
    mutationFn: (payload: { external_event_id: string; clock_offset_s?: number | null }) =>
      linkActivitySession(athleteId, activityId, payload),
    onSuccess: (activity) => {
      queryClient.setQueryData(["activity", athleteId, activityId], activity);
      invalidate();
    },
  });
}

export function useUnlinkActivitySession(athleteId: string, activityId: string) {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateActivities();
  return useMutation({
    mutationFn: () => unlinkActivitySession(athleteId, activityId),
    onSuccess: (activity) => {
      queryClient.setQueryData(["activity", athleteId, activityId], activity);
      invalidate();
    },
  });
}

// --- connections -----------------------------------------------------------------------
// A connect or sync answers before the background import has run, so the status polls for a while.

const POLL_WHILE_SYNCING_MS = 3000;

function isSyncing(runs: { status: string }[] | undefined): boolean {
  return runs?.[0]?.status === "pending";
}

export function useIntervalsStatus(athleteId: string) {
  return useQuery({
    queryKey: ["intervals", athleteId],
    queryFn: () => getIntervalsStatus(athleteId),
    enabled: athleteId !== "",
    refetchInterval: (query) => (isSyncing(query.state.data?.runs) ? POLL_WHILE_SYNCING_MS : false),
  });
}

export function useStravaStatus(athleteId: string) {
  return useQuery({
    queryKey: ["strava", athleteId],
    queryFn: () => getStravaStatus(athleteId),
    enabled: athleteId !== "",
    refetchInterval: (query) => (isSyncing(query.state.data?.runs) ? POLL_WHILE_SYNCING_MS : false),
  });
}

export function useConnectIntervals(athleteId: string) {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateActivities();
  return useMutation({
    mutationFn: (apiKey: string) => connectIntervals(athleteId, apiKey),
    onSuccess: (status) => {
      queryClient.setQueryData(["intervals", athleteId], status);
      // The first sync runs right after the response: look again shortly.
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["intervals", athleteId] });
        invalidate();
      }, 2500);
    },
  });
}

export function useSyncIntervals(athleteId: string) {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateActivities();
  return useMutation({
    mutationFn: () => syncIntervals(athleteId),
    onSuccess: () => {
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["intervals", athleteId] });
        invalidate();
      }, 2500);
    },
  });
}

export function useDisconnectIntervals(athleteId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => disconnectIntervals(athleteId),
    onSuccess: (status) => queryClient.setQueryData(["intervals", athleteId], status),
  });
}

export function useStartStravaAuthorization(athleteId: string) {
  return useMutation({ mutationFn: () => getStravaAuthorizeUrl(athleteId) });
}

export function useSyncStrava(athleteId: string) {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateActivities();
  return useMutation({
    mutationFn: () => syncStrava(athleteId),
    onSuccess: () => {
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["strava", athleteId] });
        invalidate();
      }, 2500);
    },
  });
}

export function useDisconnectStrava(athleteId: string) {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateActivities();
  return useMutation({
    mutationFn: () => disconnectStrava(athleteId),
    onSuccess: (status) => {
      queryClient.setQueryData(["strava", athleteId], status);
      invalidate();
    },
  });
}
