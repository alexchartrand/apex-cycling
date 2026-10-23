import type { Effort } from "../training/types";

export interface LapRow {
  lap: number;
  a: number | null;
  b: number | null;
}

export interface DeltaRow {
  lap: number;
  /** B's elapsed time minus A's at the end of this lap; positive = B is behind. */
  deltaMs: number;
  /** The lap's own gap (B − A). */
  lapDeltaMs: number;
}

export interface SplitRow {
  n: number;
  label: string;
  a: number | null;
  b: number | null;
}

/** Lap times side by side, lap 1 with lap 1; the shorter effort just ends early. */
export function lapRows(a: Effort, b: Effort): LapRow[] {
  const count = Math.max(a.lap_times_ms.length, b.lap_times_ms.length);
  return Array.from({ length: count }, (_, i) => ({ lap: i + 1, a: a.lap_times_ms[i] ?? null, b: b.lap_times_ms[i] ?? null }));
}

/**
 * Running gap between two efforts, lap by lap. It stops at the first lap
 * either rider didn't finish: after it the elapsed times no longer line up.
 */
export function cumulativeDelta(a: Effort, b: Effort): DeltaRow[] {
  const rows: DeltaRow[] = [];
  let total = 0;
  for (const { lap, a: timeA, b: timeB } of lapRows(a, b)) {
    if (timeA == null || timeB == null) break;
    total += timeB - timeA;
    rows.push({ lap, deltaMs: total, lapDeltaMs: timeB - timeA });
  }
  return rows;
}

/** Half-lap splits of both efforts, split 1 with split 1 (only those with a time on either side). */
export function splitRows(a: Effort, b: Effort): SplitRow[] {
  const count = Math.max(a.half_lap_splits.length, b.half_lap_splits.length);
  const rows: SplitRow[] = [];
  for (let i = 0; i < count; i++) {
    const splitA = a.half_lap_splits[i];
    const splitB = b.half_lap_splits[i];
    const reference = splitA ?? splitB;
    rows.push({ n: i + 1, label: `${reference.from_line}→${reference.to_line}`, a: splitA?.time_ms ?? null, b: splitB?.time_ms ?? null });
  }
  return rows.filter((row) => row.a != null || row.b != null);
}

/** The effort to show when the URL names none: the longest one, the earliest on a tie. */
export function defaultEffort(efforts: Effort[]): Effort | undefined {
  return efforts.reduce<Effort | undefined>((best, effort) => (!best || effort.lap_ids.length > best.lap_ids.length ? effort : best), undefined);
}

/** The effort whose first lap is `firstLapId`, else the default one. */
export function pickEffort(efforts: Effort[], firstLapId: string | null): Effort | undefined {
  return efforts.find((effort) => effort.lap_ids[0] === firstLapId) ?? defaultEffort(efforts);
}

export type Side = "a" | "b";

/** Which side has the better figure (lower by default), null on a tie or a missing value. */
export function better(a: number | null | undefined, b: number | null | undefined, direction: "lower" | "higher" = "lower"): Side | null {
  if (a == null || b == null || a === b) return null;
  return (a < b) === (direction === "lower") ? "a" : "b";
}

/** The compare page's address; a side without an effort lets the page pick one. */
export function compareHref(a: { eventId: string; firstLapId?: string }, b?: { eventId: string; firstLapId?: string }): string {
  const params = new URLSearchParams({ a: a.eventId });
  if (a.firstLapId) params.set("ae", a.firstLapId);
  if (b) {
    params.set("b", b.eventId);
    if (b.firstLapId) params.set("be", b.firstLapId);
  }
  return `/compare?${params.toString()}`;
}
