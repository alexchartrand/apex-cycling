import { parseLocalDate } from "../../i18n/format";
import type { LapDetail, SessionSummary } from "./types";

// The flying 200 is the track view sqorz names "200m" (the backend's F200
// standard event uses the same name); 250 m is assumed until a track's own
// length is set (track settings).
export const FLYING_200_VIEW_NAME = "200m";
export const FLYING_200_DISTANCE_M = 200;
export const DEFAULT_LAP_DISTANCE_M = 250;

export function flying200Ms(lap: LapDetail): number | null {
  return lap.views.find((view) => view.name === FLYING_200_VIEW_NAME)?.time_ms ?? null;
}

export type BestLap = { lap: LapDetail; index: number; value: number };

/**
 * Lowest non-null value of `getValue` across laps (first one wins ties).
 * Excluded laps never count; `index` is still the lap's position in `laps`.
 */
export function bestLap(laps: LapDetail[], getValue: (lap: LapDetail) => number | null | undefined): BestLap | null {
  let best: BestLap | null = null;
  laps.forEach((lap, index) => {
    if (lap.excluded) return;
    const value = getValue(lap);
    if (value == null) return;
    if (best == null || value < best.value) best = { lap, index, value };
  });
  return best;
}

const finishedLaps = (laps: LapDetail[]) => laps.filter((lap) => lap.whole_lap_time_ms != null);

/** Distance ridden: finished laps only (a lap the rider abandoned isn't a full lap). Null while the lap length is unknown. */
export function distanceRiddenM(laps: LapDetail[], lapLengthM: number | null | undefined): number | null {
  return lapLengthM ? finishedLaps(laps).length * lapLengthM : null;
}

/** Time spent riding finished laps, in ms. */
export function ridingTimeMs(laps: LapDetail[]): number {
  return finishedLaps(laps).reduce((sum, lap) => sum + (lap.whole_lap_time_ms ?? 0), 0);
}

const kmh = (distanceM: number, ms: number) => (distanceM / (ms / 1000)) * 3.6;

/**
 * Fastest speed of the session in km/h: the better of the quickest lap and
 * the flying 200 (excluded laps ignored). A lap needs the lap length; the
 * flying 200 is always 200 m. Null when neither can be computed.
 */
export function topSpeedKmh(laps: LapDetail[], lapLengthM: number | null | undefined): number | null {
  const candidates: number[] = [];
  const lap = bestLap(laps, (l) => l.whole_lap_time_ms);
  if (lap && lapLengthM) candidates.push(kmh(lapLengthM, lap.value));
  const f200 = bestLap(laps, flying200Ms);
  if (f200) candidates.push(kmh(FLYING_200_DISTANCE_M, f200.value));
  return candidates.length > 0 ? Math.max(...candidates) : null;
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
