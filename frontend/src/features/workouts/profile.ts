import type { ProfileSegment } from "./types";

/*
  Geometry of the intensity chart: one bar per step as ridden, x and width
  as fractions of the workout, height as a fraction of the y scale (FTP
  multiples). A step without power or RPE has no intensity and is drawn as
  a low hatched bar so its time still shows.
*/

export type BarTone = "easy" | "recovery" | "work" | "track";

export type ProfileBar = {
  x: number;
  width: number;
  /** Fraction of the chart height. */
  height: number;
  /** A power range's bottom, same scale; null without a range. */
  rangeLow: number | null;
  tone: BarTone;
  unrated: boolean;
  segment: ProfileSegment;
};

/** Where an unrated step's bar stops, in FTP multiples. */
export const UNRATED_INTENSITY = 0.4;
const MIN_SCALE = 1.2;
const MAX_SCALE = 2.5;

/** The y axis top: room above the hardest step (and above FTP), but a 300 % sprint can't flatten the rest. */
export function profileScale(segments: ProfileSegment[]): number {
  const top = Math.max(0, ...segments.map((segment) => segment.power_high ?? segment.intensity ?? 0));
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, Math.ceil(top * 1.1 * 10) / 10));
}

function toneOf(segment: ProfileSegment): BarTone {
  if (segment.kind === "warmup" || segment.kind === "cooldown") return "easy";
  if (segment.kind === "recovery") return "recovery";
  return segment.is_track ? "track" : "work";
}

export function profileBars(segments: ProfileSegment[], scale = profileScale(segments)): ProfileBar[] {
  const total = segments.reduce((end, segment) => Math.max(end, segment.start_s + segment.duration_s), 0);
  if (total <= 0) return [];
  const fraction = (value: number) => Math.min(1, value / scale);
  return segments.map((segment) => {
    const unrated = segment.intensity == null;
    const ranged = segment.power_low != null && segment.power_high != null && segment.power_high > segment.power_low;
    return {
      x: segment.start_s / total,
      width: segment.duration_s / total,
      height: fraction(ranged ? segment.power_high! : (segment.intensity ?? UNRATED_INTENSITY)),
      rangeLow: ranged ? fraction(segment.power_low!) : null,
      tone: toneOf(segment),
      unrated,
      segment,
    };
  });
}

const TICK_STEPS_S = [30, 60, 120, 300, 600, 900, 1200, 1800, 3600];

/** Round times along the x axis, at most `maxTicks` of them, 0 included. */
export function timeTicks(totalS: number, maxTicks = 6): number[] {
  if (totalS <= 0) return [];
  const step = TICK_STEPS_S.find((candidate) => totalS / candidate <= maxTicks - 1) ?? Math.ceil(totalS / (maxTicks - 1) / 3600) * 3600;
  const ticks: number[] = [];
  for (let t = 0; t <= totalS + 1e-9; t += step) ticks.push(t);
  return ticks;
}

/** A step or axis time: "0:08", "20:00", "1:20:00" (hours always spelled out, so 1:20 is never ambiguous). */
export function clockText(seconds: number): string {
  const s = Math.round(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const rest = String(s % 60).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${rest}` : `${m}:${rest}`;
}

/** A whole workout: "45 min", "1 h", "1 h 05". */
export function lengthText(seconds: number): string {
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  const rest = minutes % 60;
  return rest === 0 ? `${Math.floor(minutes / 60)} h` : `${Math.floor(minutes / 60)} h ${String(rest).padStart(2, "0")}`;
}
