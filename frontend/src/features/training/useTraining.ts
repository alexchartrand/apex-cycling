import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getProgression, getSessionDetail, listSessions, listTracks, updateTrack } from "./api";
import type { ProgressionParams, TrackUpdate } from "./types";

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
        ["tracks", "progression", "records", "session-detail"].map((key) => queryClient.invalidateQueries({ queryKey: [key] })),
      ),
  });
}
