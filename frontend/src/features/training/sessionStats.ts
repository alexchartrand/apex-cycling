import { parseLocalDate } from "../../i18n/format";
import type { LapDetail, SessionSummary } from "./types";

// "For now" assumptions carried over from the original session page; both
// become per-track settings in T3.5.
export const FLYING_200_VIEW_NAME = "200m";
export const DEFAULT_LAP_DISTANCE_M = 250;

export function flying200Ms(lap: LapDetail): number | null {
  return lap.views.find((view) => view.name === FLYING_200_VIEW_NAME)?.time_ms ?? null;
}

export type BestLap = { lap: LapDetail; index: number; value: number };

/** Lowest non-null value of `getValue` across laps (first one wins ties). */
export function bestLap(laps: LapDetail[], getValue: (lap: LapDetail) => number | null | undefined): BestLap | null {
  let best: BestLap | null = null;
  laps.forEach((lap, index) => {
    const value = getValue(lap);
    if (value == null) return;
    if (best == null || value < best.value) best = { lap, index, value };
  });
  return best;
}

/** sqorz start number when present, else 1-based position in the session. */
export function lapNumber(lap: LapDetail, index: number): number {
  return lap.start_number ?? index + 1;
}

/** Monday 00:00 (local) of the week containing `date`. */
export function startOfWeek(date: Date): Date {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const daysSinceMonday = (d.getDay() + 6) % 7;
  d.setDate(d.getDate() - daysSinceMonday);
  return d;
}

export type WeekSummary = { sessions: number; laps: number; trackSeconds: number };

/** Totals for sessions whose date falls in [weekStart, weekStart + 7 days). */
export function summarizeWeek(sessions: SessionSummary[], weekStart: Date): WeekSummary {
  const weekEnd = new Date(weekStart);
  weekEnd.setDate(weekEnd.getDate() + 7);
  const inWeek = sessions.filter((s) => {
    const d = parseLocalDate(s.event_date);
    return d >= weekStart && d < weekEnd;
  });
  return {
    sessions: inWeek.length,
    laps: inWeek.reduce((sum, s) => sum + s.lap_count, 0),
    trackSeconds: inWeek.reduce((sum, s) => {
      if (!s.first_lap_at || !s.last_lap_at) return sum;
      return sum + (new Date(s.last_lap_at).getTime() - new Date(s.first_lap_at).getTime()) / 1000;
    }, 0),
  };
}

/** Groups newest-first sessions under "YYYY-MM" keys, preserving order. */
export function groupByMonth(sessions: SessionSummary[]): { month: string; sessions: SessionSummary[] }[] {
  const groups: { month: string; sessions: SessionSummary[] }[] = [];
  for (const session of sessions) {
    const month = session.event_date.slice(0, 7);
    const last = groups[groups.length - 1];
    if (last?.month === month) last.sessions.push(session);
    else groups.push({ month, sessions: [session] });
  }
  return groups;
}
