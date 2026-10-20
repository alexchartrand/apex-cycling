/*
  The tools' inputs live in the URL query string, so any tool state is a link
  that can be shared or bookmarked (a coach sends a pursuit schedule, a rider
  keeps their setup). A value not in the URL falls back to the athlete's
  profile or track (see useToolInputs), then to a typical default. The raw
  text is kept as typed, so a half-typed "0." doesn't get rewritten.
*/
import { parseTimeInput } from "../records/timeInput";

export type NumberSpec = { param: string; min: number; max: number; step: number; integer?: boolean };

export const NUMBER_FIELDS = {
  riderKg: { param: "rider", min: 20, max: 250, step: 0.1 },
  bikeKg: { param: "bike", min: 0, max: 40, step: 0.1 },
  cda: { param: "cda", min: 0.1, max: 0.6, step: 0.001 },
  crr: { param: "crr", min: 0.001, max: 0.02, step: 0.0001 },
  efficiencyPct: { param: "eff", min: 80, max: 100, step: 0.1 },
  tempC: { param: "temp", min: -30, max: 50, step: 0.5 },
  elevationM: { param: "elev", min: -400, max: 5000, step: 1 },
  humidityPct: { param: "rh", min: 0, max: 100, step: 1 },
  pressureHpa: { param: "hpa", min: 500, max: 1100, step: 0.1 },
  lapM: { param: "lap", min: 100, max: 1000, step: 0.01 },
  distanceM: { param: "dist", min: 50, max: 50_000, step: 1 },
  powerW: { param: "power", min: 1, max: 3000, step: 1 },
  chainring: { param: "ring", min: 30, max: 80, step: 1, integer: true },
  cog: { param: "cog", min: 10, max: 30, step: 1, integer: true },
  rolloutM: { param: "rollout", min: 1.5, max: 2.5, step: 0.001 },
} as const satisfies Record<string, NumberSpec>;

export type NumberKey = keyof typeof NUMBER_FIELDS;

/** Target time, typed like "4:15.0" (parsed by the records time parser). */
export const TIME_PARAM = "time";
export const START_PARAM = "start";
export const TRACK_PARAM = "track";
export const MODE_PARAM = "mode";

export type StartKind = "standing" | "flying";

/** Used when neither the URL nor the profile/track gives a value. */
export const FALLBACKS: Record<NumberKey, number | null> = {
  riderKg: 75,
  bikeKg: 8,
  cda: 0.22,
  crr: 0.0025,
  efficiencyPct: 98,
  tempC: 20,
  elevationM: 0,
  humidityPct: 50,
  pressureHpa: null, // optional: estimated from the elevation when blank
  lapM: 250,
  distanceM: 4000,
  powerW: 400,
  chainring: 52,
  cog: 14,
  rolloutM: 2.1,
};
export const FALLBACK_TIME = "4:30";

/** "0,22" or "0.22" → 0.22; null for blank or junk. */
export function parseNumber(raw: string): number | null {
  const text = raw.trim().replace(",", ".");
  if (text === "" || !/^-?\d*\.?\d+$|^-?\d+\.$/.test(text)) return null;
  const value = Number(text);
  return Number.isFinite(value) ? value : null;
}

export type FieldState = { raw: string; value: number | null; invalid: boolean };

export function readNumberField(key: NumberKey, raw: string): FieldState {
  const spec: NumberSpec = NUMBER_FIELDS[key];
  if (raw.trim() === "") return { raw, value: null, invalid: FALLBACKS[key] !== null };
  const value = parseNumber(raw);
  const invalid =
    value === null || value < spec.min || value > spec.max || (spec.integer === true && !Number.isInteger(value));
  return { raw, value: invalid ? null : value, invalid };
}

export function readTimeField(raw: string): { raw: string; seconds: number | null; invalid: boolean } {
  const ms = parseTimeInput(raw);
  return { raw, seconds: ms === null ? null : ms / 1000, invalid: ms === null };
}

/** URL value, else the profile/track default, else the fallback, as text. */
export function rawValue(params: URLSearchParams, key: NumberKey, prefill: Partial<Record<NumberKey, number | null>>): string {
  const fromUrl = params.get(NUMBER_FIELDS[key].param);
  if (fromUrl !== null) return fromUrl;
  const value = prefill[key] ?? FALLBACKS[key];
  return value === null ? "" : String(value);
}

/**
 * A link that reproduces exactly what's on screen: every value in effect is
 * written out, so the recipient's own profile doesn't change the numbers.
 */
export function shareQuery(entries: Record<string, string | null | undefined>): string {
  const params = new URLSearchParams();
  for (const [param, value] of Object.entries(entries)) {
    if (value != null && value.trim() !== "") params.set(param, value.trim());
  }
  return params.toString();
}
