import { useQueries } from "@tanstack/react-query";
import { useState } from "react";
import { parseLocalDate } from "../../i18n/format";
import { sessionsRangeQuery, useSessionsRange } from "../training/useTraining";
import { addDays, dayBounds } from "./dayRange";
import { localDay } from "./format";
import { monthCalendar } from "./logItems";
import { logWindows, newestMonth, pageWindow, type DayWindow } from "./logPages";
import { activitiesRangeQuery, useActivitiesRange } from "./useActivities";

/** The month (`YYYY-MM`) of the newest session or activity before local day `before` (of all of them when null); undefined while loading. */
function useNewestMonthBefore(athleteId: string, before: string | null, enabled: boolean) {
  const sessions = useSessionsRange(athleteId, before ? { to: addDays(before, -1), limit: 1 } : { limit: 1 }, enabled);
  const activities = useActivitiesRange(athleteId, before ? { end: parseLocalDate(before).toISOString(), limit: 1 } : { limit: 1 }, enabled);
  if (!sessions.data || !activities.data) return { month: undefined, isError: sessions.isError || activities.isError };
  const activity = activities.data[0];
  return { month: newestMonth(sessions.data[0]?.event_date, activity ? localDay(activity.start_time) : null), isError: false };
}

function windowQueries(athleteId: string, window: DayWindow, enabled: boolean) {
  const bounds = dayBounds(window.from, window.to ?? window.from);
  return {
    sessions: sessionsRangeQuery(athleteId, window.to ? { from: window.from, to: window.to } : { from: window.from }, enabled),
    activities: activitiesRangeQuery(athleteId, window.to ? bounds : { start: bounds.start }, enabled),
  };
}

/**
 * The Log's list: the newest `LOG_PAGE_MONTHS` months that have anything,
 * then `loadMore` adds the next ones that do (skipping empty stretches). Each
 * page is a plain sessions and activities range query, so whatever refreshes
 * those refreshes the list.
 */
export function useLogList(athleteId: string, enabled: boolean) {
  const [loaded, setLoaded] = useState<{ athleteId: string; older: Required<DayWindow>[] }>({ athleteId, older: [] });
  const older = loaded.athleteId === athleteId ? loaded.older : [];
  const newest = useNewestMonthBefore(athleteId, null, enabled);
  const windows = newest.month ? logWindows(newest.month, older) : [];
  const queries = windows.map((window) => windowQueries(athleteId, window, enabled));
  const sessionPages = useQueries({ queries: queries.map((q) => q.sessions) });
  const activityPages = useQueries({ queries: queries.map((q) => q.activities) });
  const oldestFrom = windows.at(-1)?.from ?? null;
  const next = useNewestMonthBefore(athleteId, oldestFrom, enabled && oldestFrom !== null);

  const pending = (i: number) => sessionPages[i]?.isPending || activityPages[i]?.isPending;
  const lastPending = windows.length > 0 && pending(windows.length - 1);
  return {
    sessions: sessionPages.flatMap((q) => q.data ?? []),
    activities: activityPages.flatMap((q) => q.data ?? []),
    isLoading: enabled && (newest.month === undefined || (older.length === 0 && lastPending)) && !newest.isError,
    isError: newest.isError || sessionPages.some((q) => q.isError),
    hasMore: next.month != null,
    loadingMore: older.length > 0 && lastPending,
    loadMore: () => {
      if (next.month) setLoaded({ athleteId, older: [...older, pageWindow(next.month)] });
    },
  };
}

/** The days a month's calendar grid shows, outside days included. */
export function useLogMonth(athleteId: string, year: number, monthIndex: number, enabled: boolean) {
  const weeks = monthCalendar(year, monthIndex, []);
  const window = { from: weeks[0][0].day, to: weeks[weeks.length - 1][6].day };
  const queries = windowQueries(athleteId, window, enabled);
  const [sessions, activities] = useQueries({ queries: [queries.sessions, queries.activities] });
  return {
    sessions: sessions.data ?? [],
    activities: activities.data ?? [],
    isLoading: enabled && (sessions.isPending || activities.isPending),
    isError: sessions.isError,
  };
}
