import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { listInsights, listSessionInsights } from "./api";
import { FEED_DAYS, FEED_LIMIT, newInsights } from "./insights";
import type { Insight } from "./types";

const feedKey = (athleteId: string) => ["insights", athleteId, "feed"] as const;

/** The headlines of the last weeks of sessions ("What's new"). */
export function useInsightsFeed(athleteId: string) {
  return useQuery({
    queryKey: feedKey(athleteId),
    queryFn: () => listInsights(athleteId, FEED_DAYS, FEED_LIMIT),
    enabled: athleteId !== "",
  });
}

export function useSessionInsights(athleteId: string, eventId: string) {
  return useQuery({
    queryKey: ["insights", athleteId, "session", eventId],
    queryFn: () => listSessionInsights(athleteId, eventId),
    enabled: athleteId !== "" && eventId !== "",
  });
}

/**
 * For a sync: `watch()` remembers the headlines known now and returns a
 * function that, once the sync is done, refetches them and returns the ones
 * that appeared. Nothing else goes through here so the caller decides how to
 * announce them.
 */
export function useNewInsightsAfter(athleteId: string) {
  const queryClient = useQueryClient();
  return useCallback(async (): Promise<() => Promise<Insight[]>> => {
    const key = feedKey(athleteId);
    const fetchFeed = (staleTime: number) =>
      queryClient.fetchQuery({ queryKey: key, queryFn: () => listInsights(athleteId, FEED_DAYS, FEED_LIMIT), staleTime });
    const before = await fetchFeed(60_000).catch(() => null);
    return async () => {
      await queryClient.invalidateQueries({ queryKey: ["insights", athleteId] });
      const after = await fetchFeed(0).catch(() => null);
      return before && after ? newInsights(before, after) : [];
    };
  }, [athleteId, queryClient]);
}

