/*
  Pure helpers for the aero lab: the assumptions form, the scatter's points and
  fit line, the hand-picked lap selection, and what a CdA difference is worth
  on the track (through the same physics model as the tools).
*/
import type { Activity } from "../activities/types";
import { G, makeSetup, simulate } from "../tools/physics";
import { parseNumber } from "../tools/toolInputs";
import type { SessionSummary } from "../training/types";
import type { AeroConditions, AeroFit, AeroInputs, AeroPoint } from "./types";

export const INPUT_KEYS = ["temp_c", "elevation_m", "pressure_hpa", "humidity_pct", "rider_kg", "bike_kg", "crr"] as const;
export type InputKey = (typeof INPUT_KEYS)[number];

/** Same bounds as the API (`app/aero/schemas.py`). */
export const INPUT_BOUNDS: Record<InputKey, { min: number; max: number }> = {
  temp_c: { min: -30, max: 50 },
  elevation_m: { min: -400, max: 5000 },
  pressure_hpa: { min: 500, max: 1100 },
  humidity_pct: { min: 0, max: 100 },
  rider_kg: { min: 20, max: 250 },
  bike_kg: { min: 0, max: 40 },
  crr: { min: 0.001, max: 0.02 },
};

/** The form keeps what was typed; blank means "use the default". */
export type InputDraft = Record<InputKey, string>;

export const EMPTY_DRAFT: InputDraft = Object.fromEntries(INPUT_KEYS.map((key) => [key, ""])) as InputDraft;

export function readInputs(draft: InputDraft): { inputs: AeroInputs; invalid: InputKey[] } {
  const invalid: InputKey[] = [];
  const inputs = {} as AeroInputs;
  for (const key of INPUT_KEYS) {
    const raw = draft[key];
    const value = parseNumber(raw);
    const { min, max } = INPUT_BOUNDS[key];
    if (raw.trim() !== "" && (value === null || value < min || value > max)) invalid.push(key);
    inputs[key] = value !== null && value >= min && value <= max ? value : null;
  }
  return { inputs, invalid };
}

export function draftFromInputs(inputs: AeroInputs): InputDraft {
  return Object.fromEntries(INPUT_KEYS.map((key) => [key, inputs[key] == null ? "" : String(inputs[key])])) as InputDraft;
}

/** Sessions with a linked recording that has power: the only ones that can give a CdA. */
export function sessionsWithPower(sessions: SessionSummary[], activities: Activity[]): SessionSummary[] {
  const powered = new Set(activities.filter((a) => a.has_power && a.external_event_id).map((a) => a.external_event_id));
  return sessions.filter((s) => powered.has(s.external_event_id));
}

/** Starts from the laps the estimate used when nothing was picked by hand yet. */
export function toggleLap(points: AeroPoint[], selection: string[] | null, lapId: string): string[] {
  const current = selection ?? points.filter((p) => p.used).map((p) => p.lap_id);
  return current.includes(lapId) ? current.filter((id) => id !== lapId) : [...current, lapId];
}

export type ScatterPoint = {
  /** Speed squared (m²/s²): the force line is straight in it. */
  x: number;
  /** Resistive force (N). */
  y: number;
  lapId: string;
  used: boolean;
  speedKmh: number;
  powerW: number | null;
  cdaM2: number | null;
  effortIndex: number;
  lapInEffort: number;
};

export function scatterPoints(points: AeroPoint[]): ScatterPoint[] {
  return points
    .filter((p) => p.resistance_n !== null)
    .map((p) => ({
      x: p.speed_ms ** 2,
      y: p.resistance_n as number,
      lapId: p.lap_id,
      used: p.used,
      speedKmh: p.speed_ms * 3.6,
      powerW: p.power_w,
      cdaM2: p.cda_m2,
      effortIndex: p.effort_index,
      lapInEffort: p.lap_in_effort,
    }));
}

export function totalMassKg(conditions: AeroConditions): number | null {
  return conditions.rider_kg === null ? null : conditions.rider_kg + conditions.bike_kg;
}

/** The fitted force line, Crr·m·g + ½ρ·CdA·v², across the points' range. */
export function fitLine(fit: AeroFit, conditions: AeroConditions, xs: number[]): { x: number; y: number }[] {
  const mass = totalMassKg(conditions);
  if (mass === null || xs.length === 0) return [];
  const low = Math.min(...xs) * 0.95;
  const high = Math.max(...xs) * 1.05;
  const at = (x: number) => fit.crr * mass * G + 0.5 * conditions.rho * fit.cda_m2 * x;
  return [
    { x: low, y: at(low) },
    { x: high, y: at(high) },
  ];
}

/** The two CdAs are within their combined standard error of each other. */
export function withinNoise(a: AeroFit, b: AeroFit): boolean {
  if (a.cda_se_m2 === null || b.cda_se_m2 === null) return false;
  return Math.abs(a.cda_m2 - b.cda_m2) < Math.hypot(a.cda_se_m2, b.cda_se_m2);
}

export type WorthScenario = { powerW: number; distanceM: number; standing: boolean };

/**
 * Seconds a CdA gains (negative) or loses against the baseline's over the
 * scenario, everything else being the baseline's: mass, air and Crr.
 */
export function worthSeconds(
  cdaM2: number,
  baseline: { fit: AeroFit; conditions: AeroConditions },
  scenario: WorthScenario,
): number | null {
  const mass = totalMassKg(baseline.conditions);
  if (mass === null) return null;
  const time = (cda: number) =>
    simulate(
      scenario.distanceM,
      scenario.powerW,
      makeSetup({ massKg: mass, cdaM2: cda, rho: baseline.conditions.rho, crr: baseline.fit.crr }),
      { standing: scenario.standing },
    )?.timeS ?? null;
  const base = time(baseline.fit.cda_m2);
  const other = time(cdaM2);
  return base === null || other === null ? null : other - base;
}
