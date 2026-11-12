import { queryOptions, useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getProgression,
  getSessionDetail,
  getSessionNeighbours,
  labelEffort,
  listEfforts,
  listSessions,
  type SessionsRange,
  listTracks,
  updateLap,
  updateSession,
  updateTrack,
} from "./api";
import { mergeChoices, missingChoices } from "./sessionChoices";
import type { LapUpdate, ProgressionParams, SessionUpdate, TrackUpdate } from "./types";

/** A bounded slice of the list (see `SessionsRange`). Under the `["sessions", athleteId]` prefix, so anything that invalidates the list refreshes it. */
export function useSessionsRange(athleteId: string, range: SessionsRange, enabled = true) {
  return useQuery(sessionsRangeQuery(athleteId, range, enabled));
}

export function sessionsRangeQuery(athleteId: string, range: SessionsRange, enabled = true) {
  return queryOptions({
    queryKey: ["sessions", athleteId, range],
    queryFn: () => listSessions(athleteId, range),
    enabled: enabled && athleteId !== "",
  });
}

export const SESSION_PAGE_SIZE = 50;

/** The newest-first list, `SESSION_PAGE_SIZE` at a time, for pickers. */
export function useSessionPages(athleteId: string, filter: { powered?: boolean } = {}) {
  return useInfiniteQuery({
    queryKey: ["sessions", athleteId, "pages", filter],
    queryFn: ({ pageParam }) => listSessions(athleteId, { ...filter, limit: SESSION_PAGE_SIZE, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => (last.length < SESSION_PAGE_SIZE ? undefined : pages.length * SESSION_PAGE_SIZE),
    enabled: athleteId !== "",
  });
}

/**
 * The sessions a picker offers: the newest pages, plus the `selected` ones
 * (from the URL, say) even when they're older than what is loaded.
 */
export function useSessionChoices(athleteId: string, selected: string[], filter: { powered?: boolean } = {}) {
  const pages = useSessionPages(athleteId, filter);
  const loaded = pages.data?.pages.flat() ?? [];
  const missing = pages.data ? missingChoices(loaded, selected) : [];
  const extra = useSessionsRange(athleteId, { eventIds: missing }, missing.length > 0);
  return {
    sessions: pages.data ? mergeChoices(loaded, missing.length > 0 ? (extra.data ?? []) : []) : undefined,
    isLoading: pages.isLoading,
    isError: pages.isError,
    hasMore: pages.hasNextPage,
    loadMore: () => void pages.fetchNextPage(),
    loadingMore: pages.isFetchingNextPage,
  };
}

export function useSessionNeighbours(athleteId: string, eventId: string) {
  return useQuery({
    queryKey: ["sessions", athleteId, "neighbours", eventId],
    queryFn: () => getSessionNeighbours(athleteId, eventId),
    enabled: athleteId !== "" && eventId !== "",
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
    // The title shows in the list and the header too, and the race mark feeds the race calendar and the season tiles.
    onSuccess: () =>
      Promise.all(
        [
          ["session-detail", athleteId, eventId],
          ["sessions", athleteId],
          ["competitions", athleteId],
          ["season-summary", athleteId],
        ].map((queryKey) =>
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
