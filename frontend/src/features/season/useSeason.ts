import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  closeCalendarFeed,
  createCompetition,
  createSeason,
  deleteCompetition,
  deleteSeason,
  getCalendarFeed,
  getSeason,
  listCompetitions,
  listSeasons,
  makeCalendarFeed,
  updateCompetition,
  updateSeason,
} from "./api";
import type { CompetitionWrite, SeasonWrite } from "./types";

export function useSeasons(athleteId: string) {
  return useQuery({ queryKey: ["seasons", athleteId], queryFn: () => listSeasons(athleteId), enabled: athleteId !== "" });
}

export function useSeasonSummary(athleteId: string, seasonId: string) {
  return useQuery({
    queryKey: ["season-summary", athleteId, seasonId],
    queryFn: () => getSeason(athleteId, seasonId),
    enabled: athleteId !== "" && seasonId !== "",
  });
}

export function useCompetitions(athleteId: string) {
  return useQuery({ queryKey: ["competitions", athleteId], queryFn: () => listCompetitions(athleteId), enabled: athleteId !== "" });
}

/** 403 for anyone but the athlete's side, which is a normal answer, so it isn't retried. */
export function useCalendarFeed(athleteId: string) {
  return useQuery({ queryKey: ["calendar-feed", athleteId], queryFn: () => getCalendarFeed(athleteId), enabled: athleteId !== "", retry: false });
}

function useInvalidate(athleteId: string, keys: string[]) {
  const queryClient = useQueryClient();
  return () => Promise.all(keys.map((key) => queryClient.invalidateQueries({ queryKey: [key, athleteId] })));
}

export function useSaveSeason(athleteId: string) {
  const invalidate = useInvalidate(athleteId, ["seasons", "season-summary"]);
  return useMutation({
    mutationFn: ({ id, payload }: { id?: string; payload: SeasonWrite }) =>
      id ? updateSeason(athleteId, id, payload) : createSeason(athleteId, payload),
    onSuccess: invalidate,
  });
}

export function useDeleteSeason(athleteId: string) {
  const invalidate = useInvalidate(athleteId, ["seasons", "season-summary"]);
  return useMutation({ mutationFn: (id: string) => deleteSeason(athleteId, id), onSuccess: invalidate });
}

export function useSaveCompetition(athleteId: string) {
  const invalidate = useInvalidate(athleteId, ["competitions"]);
  return useMutation({
    mutationFn: ({ id, payload }: { id?: string; payload: CompetitionWrite }) =>
      id ? updateCompetition(athleteId, id, payload) : createCompetition(athleteId, payload),
    onSuccess: invalidate,
  });
}

export function useDeleteCompetition(athleteId: string) {
  const invalidate = useInvalidate(athleteId, ["competitions"]);
  return useMutation({ mutationFn: (id: string) => deleteCompetition(athleteId, id), onSuccess: invalidate });
}

export function useMakeCalendarFeed(athleteId: string) {
  const invalidate = useInvalidate(athleteId, ["calendar-feed"]);
  return useMutation({ mutationFn: () => makeCalendarFeed(athleteId), onSuccess: invalidate });
}

export function useCloseCalendarFeed(athleteId: string) {
  const invalidate = useInvalidate(athleteId, ["calendar-feed"]);
  return useMutation({ mutationFn: () => closeCalendarFeed(athleteId), onSuccess: invalidate });
}
