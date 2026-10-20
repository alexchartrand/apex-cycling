import type { PowerCurvePoint } from "./types";

export interface CurveRow {
  duration_s: number;
  a: number | null;
  b: number | null;
}

/**
 * Two ranges' power curves on one duration axis. `weightKg` turns watts into
 * W/kg (per range, since weight changes) when given.
 */
export function compareCurves(
  a: PowerCurvePoint[],
  b: PowerCurvePoint[],
  weights: { a?: number | null; b?: number | null } = {},
): CurveRow[] {
  const scale = (points: PowerCurvePoint[], weight?: number | null) =>
    new Map(points.map((p) => [p.duration_s, weight ? p.power_w / weight : p.power_w]));
  const left = scale(a, weights.a);
  const right = scale(b, weights.b);
  return [...new Set([...left.keys(), ...right.keys()])]
    .sort((x, y) => x - y)
    .map((duration_s) => ({ duration_s, a: left.get(duration_s) ?? null, b: right.get(duration_s) ?? null }));
}

/** The efforts riders quote, picked from a curve. */
export const HEADLINE_DURATIONS_S = [5, 60, 300, 1200] as const;

export function headlinePowers(points: PowerCurvePoint[]): { duration_s: number; point: PowerCurvePoint | null }[] {
  const byDuration = new Map(points.map((p) => [p.duration_s, p]));
  return HEADLINE_DURATIONS_S.map((duration_s) => ({ duration_s, point: byDuration.get(duration_s) ?? null }));
}

/** Percentage change of `now` over `before`, null when either is missing. */
export function changePercent(before: number | null, now: number | null): number | null {
  return before == null || now == null || before === 0 ? null : ((now - before) / before) * 100;
}

export type RangeKey = "28d" | "90d" | "365d" | "all";

/** ISO instants bounding a rolling range ending now (or ending `ago` before now). */
export function rangeBounds(key: RangeKey, now: Date, endsDaysAgo = 0): { start?: string; end?: string } {
  if (key === "all") return endsDaysAgo === 0 ? {} : { end: new Date(now.getTime() - endsDaysAgo * 86_400_000).toISOString() };
  const days = { "28d": 28, "90d": 90, "365d": 365 }[key];
  const end = new Date(now.getTime() - endsDaysAgo * 86_400_000);
  const start = new Date(end.getTime() - days * 86_400_000);
  return { start: start.toISOString(), end: endsDaysAgo === 0 ? undefined : end.toISOString() };
}
