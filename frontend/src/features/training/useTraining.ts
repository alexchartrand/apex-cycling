import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getProgression,
  getSessionDetail,
  labelEffort,
  listEfforts,
  listSessions,
  listTracks,
  updateLap,
  updateSession,
  updateTrack,
} from "./api";
import type { LapUpdate, ProgressionParams, SessionUpdate, TrackUpdate } from "./types";

export function useSessions(athleteId: string) {
  return useQuery({
    queryKey: ["sessions", athleteId],
    queryFn: () => listSessions(athleteId),
    enabled: athleteId !== "",
  });
}

export function useTracks(athleteId: string) {
  return useQuery({
    queryKey: ["tracks", athleteId],
    queryFn: () => listTracks(athleteId),
    enabled: athleteId !== "",
  });
}

export function useSessionDetail(athleteId: string, eventId: string) {
  return useQuery({
    queryKey: ["session-detail", athleteId, eventId],
    queryFn: () => getSessionDetail(athleteId, eventId),
    enabled: athleteId !== "" && eventId !== "",
  });
}

export function useProgression(athleteId: string, params: ProgressionParams | null) {
  return useQuery({
    queryKey: ["progression", athleteId, params],
    queryFn: () => getProgression(athleteId, params!),
    enabled: params !== null,
  });
}

/** Saves a track's settings; a new length changes records and distances, so those refetch too. */
export function useUpdateTrack(trackId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TrackUpdate) => updateTrack(trackId, payload),
    onSuccess: () =>
      Promise.all(
        ["tracks", "club-tracks", "progression", "records", "session-detail"].map((key) => queryClient.invalidateQueries({ queryKey: [key] })),
      ),
  });
}

export function useSessionEfforts(athleteId: string, eventId: string) {
  return useQuery({
    queryKey: ["session-efforts", athleteId, eventId],
    queryFn: () => listEfforts(athleteId, eventId),
    enabled: athleteId !== "" && eventId !== "",
  });
}

export function useUpdateSession(athleteId: string, eventId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SessionUpdate) => updateSession(athleteId, eventId, payload),
    // The title shows in the list and the header too.
    onSuccess: () =>
      Promise.all(
        [["session-detail", athleteId, eventId], ["sessions", athleteId]].map((queryKey) =>
          queryClient.invalidateQueries({ queryKey }),
        ),
      ),
  });
}

/** Excluding a lap changes bests, records, efforts and progression, so all of those refetch. */
export function useUpdateLap(athleteId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ lapId, ...payload }: LapUpdate & { lapId: string }) => updateLap(athleteId, lapId, payload),
    onSuccess: () =>
      Promise.all(
        ["session-detail", "session-efforts", "records", "progression"].map((key) =>
          queryClient.invalidateQueries({ queryKey: [key] }),
        ),
      ),
  });
}

export function useLabelEffort(athleteId: string, eventId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ firstLapId, label }: { firstLapId: string; label: string | null }) =>
      labelEffort(athleteId, eventId, firstLapId, label),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["session-efforts", athleteId, eventId] }),
  });
}
