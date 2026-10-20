import { EVENT_DISTANCE_M, STANDARD_EVENT_KEYS, type StandardEventKey } from "../records/types";
import type { ProgressionParams, ProgressionPoint, TrackSummary } from "./types";

export type StartChoice = "any" | "standing" | "flying";

export const EVENT_PREFIX = "event:";
export const VIEW_PREFIX = "view:";

/** Standard events that are whole laps (the flying 200 is a track view, listed with the views). */
export const LAP_EVENT_KEYS = STANDARD_EVENT_KEYS.filter((key) => key !== "f200");

export const isLapEvent = (metricKey: string): metricKey is `${typeof EVENT_PREFIX}${StandardEventKey}` =>
  metricKey.startsWith(EVENT_PREFIX) && (LAP_EVENT_KEYS as readonly string[]).includes(metricKey.slice(EVENT_PREFIX.length));

/** Standard events need whole laps, so only tracks whose lap length is set offer them. */
export function availableEvents(track: TrackSummary | undefined): StandardEventKey[] {
  return track?.length_m != null ? [...LAP_EVENT_KEYS] : [];
}

/** A flying lap is only ever flying; the other standard distances start standing; a free distance has no preference. */
export function defaultStart(metricKey: string): StartChoice {
  if (!isLapEvent(metricKey)) return "any";
  return metricKey === `${EVENT_PREFIX}lap` ? "flying" : "standing";
}

/** Whether the start-type filter does anything: whole-lap distances on a track with a known length. */
export function startTypeApplies(metricKey: string, track: TrackSummary | undefined): boolean {
  return track?.length_m != null && (isLapEvent(metricKey) || metricKey === "custom_distance");
}

export function buildProgressionParams(input: {
  track: TrackSummary | undefined;
  metricKey: string;
  distance: string;
  start: StartChoice;
  from: string;
  to: string;
}): ProgressionParams | null {
  const { track, metricKey, distance, start } = input;
  if (!track) return null;
  const base = { from: input.from || undefined, to: input.to || undefined };
  const startType = start === "any" || !startTypeApplies(metricKey, track) ? undefined : start;

  if (metricKey === "lap_time") return { ...base, metric: "lap_time", track_id: track.id };
  if (metricKey.startsWith(VIEW_PREFIX)) return { ...base, metric: "view", track_view_id: metricKey.slice(VIEW_PREFIX.length) };
  if (metricKey === "custom_distance") {
    const metres = Number(distance);
    if (!distance || Number.isNaN(metres) || metres <= 0) return null;
    return { ...base, metric: "custom_distance", track_id: track.id, distance_m: metres, start_type: startType };
  }
  if (isLapEvent(metricKey) && track.length_m != null) {
    const key = metricKey.slice(EVENT_PREFIX.length) as StandardEventKey;
    return {
      ...base,
      metric: "custom_distance",
      track_id: track.id,
      distance_m: EVENT_DISTANCE_M[key] ?? track.length_m,
      start_type: startType,
    };
  }
  return null;
}

export type PersonalBestPoint = { t: number; pbMs: number };

/**
 * The running personal best over a progression: at each session, the fastest
 * time so far. Drawn as a step line it shows when records were set.
 */
export function personalBestLine(points: { t: number; timeMs: number }[]): PersonalBestPoint[] {
  const line: PersonalBestPoint[] = [];
  let best = Infinity;
  for (const point of [...points].sort((a, b) => a.t - b.t)) {
    best = Math.min(best, point.timeMs);
    line.push({ t: point.t, pbMs: best });
  }
  return line;
}

/** Sessions whose point set a new personal best (strictly faster than every earlier one). */
export function recordSessions(points: ProgressionPoint[]): Set<string> {
  const ids = new Set<string>();
  let best = Infinity;
  for (const point of [...points].sort((a, b) => a.event_date.localeCompare(b.event_date))) {
    if (point.time_ms < best) ids.add(point.external_event_id);
    best = Math.min(best, point.time_ms);
  }
  return ids;
}
