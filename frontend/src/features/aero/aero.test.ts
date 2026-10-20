import { describe, expect, it } from "vitest";
import type { Activity } from "../activities/types";
import { G, makeSetup, simulate } from "../tools/physics";
import type { SessionSummary } from "../training/types";
import {
  EMPTY_DRAFT,
  draftFromInputs,
  fitLine,
  readInputs,
  scatterPoints,
  sessionsWithPower,
  toggleLap,
  withinNoise,
  worthSeconds,
} from "./aero";
import type { AeroConditions, AeroFit, AeroPoint } from "./types";

const conditions: AeroConditions = {
  temp_c: 20, elevation_m: 0, pressure_hpa: null, humidity_pct: 50, rho: 1.2,
  rider_kg: 72, rider_kg_date: "2026-06-01", bike_kg: 8, efficiency: 0.98,
};  // prettier-ignore
const fit: AeroFit = {
  cda_m2: 0.22, crr: 0.0025, crr_source: "fitted", r_squared: 0.98, cda_se_m2: 0.004,
  laps_used: 12, speed_ms: 15, power_w: 420, speed_spread: 0.2,
};  // prettier-ignore

function point(id: string, used: boolean, overrides: Partial<AeroPoint> = {}): AeroPoint {
  return {
    lap_id: id, start_time: "2026-06-01T18:00:00Z", effort_index: 1, lap_in_effort: 2, time_s: 16.7,
    speed_ms: 15, power_w: 400, resistance_n: 26, cda_m2: 0.22, issue: used ? null : "unsteady_speed", used, ...overrides,
  };  // prettier-ignore
}

describe("readInputs", () => {
  it("treats blanks as defaults, accepts a decimal comma and flags out-of-range values", () => {
    const { inputs, invalid } = readInputs({ ...EMPTY_DRAFT, rider_kg: "71,5", crr: "0.5", temp_c: "abc" });
    expect(inputs.rider_kg).toBe(71.5);
    expect(inputs.crr).toBeNull();
    expect(inputs.temp_c).toBeNull();
    expect(inputs.bike_kg).toBeNull();
    expect(invalid.sort()).toEqual(["crr", "temp_c"]);
  });

  it("round-trips a saved test's inputs", () => {
    const draft = draftFromInputs({ ...readInputs(EMPTY_DRAFT).inputs, bike_kg: 8.2, crr: 0.003 });
    expect(draft.bike_kg).toBe("8.2");
    expect(draft.rider_kg).toBe("");
    expect(readInputs(draft).inputs).toMatchObject({ bike_kg: 8.2, crr: 0.003, rider_kg: null });
  });
});

describe("sessionsWithPower", () => {
  it("keeps sessions with a linked recording that has power", () => {
    const sessions = ["s1", "s2", "s3"].map((id) => ({ external_event_id: id }) as SessionSummary);
    const activities = [
      { external_event_id: "s1", has_power: true },
      { external_event_id: "s2", has_power: false },
      { external_event_id: null, has_power: true },
    ] as Activity[];
    expect(sessionsWithPower(sessions, activities).map((s) => s.external_event_id)).toEqual(["s1"]);
  });
});

describe("toggleLap", () => {
  const points = [point("a", true), point("b", false), point("c", true)];

  it("starts from the automatic pick", () => {
    expect(toggleLap(points, null, "b")).toEqual(["a", "c", "b"]);
    expect(toggleLap(points, null, "a")).toEqual(["c"]);
  });

  it("then edits the hand-picked list", () => {
    expect(toggleLap(points, ["b"], "b")).toEqual([]);
  });
});

describe("scatter", () => {
  it("plots speed squared against force and skips laps without power", () => {
    const rows = scatterPoints([point("a", true), point("b", false, { power_w: null, resistance_n: null })]);
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ x: 225, y: 26, used: true, lapId: "a" });
    expect(rows[0].speedKmh).toBeCloseTo(54);
  });

  it("draws the fitted line across the points", () => {
    const [low, high] = fitLine(fit, conditions, [100, 225]);
    expect(low.x).toBeCloseTo(95);
    expect(high.x).toBeCloseTo(236.25);
    expect(low.y).toBeCloseTo(0.0025 * 80 * G + 0.6 * 0.22 * 95);
    expect(fitLine(fit, { ...conditions, rider_kg: null }, [100])).toEqual([]);
  });
});

describe("comparing setups", () => {
  it("calls a difference smaller than the combined error noise", () => {
    expect(withinNoise(fit, { ...fit, cda_m2: 0.225 })).toBe(true);
    expect(withinNoise(fit, { ...fit, cda_m2: 0.21 })).toBe(false);
    expect(withinNoise(fit, { ...fit, cda_se_m2: null })).toBe(false);
  });

  it("turns a CdA difference into seconds over the distance", () => {
    const scenario = { powerW: 420, distanceM: 4000, standing: true };
    const gained = worthSeconds(0.21, { fit, conditions }, scenario);
    const setup = (cda: number) => makeSetup({ massKg: 80, cdaM2: cda, rho: 1.2, crr: 0.0025 });
    const expected = simulate(4000, 420, setup(0.21))!.timeS - simulate(4000, 420, setup(0.22))!.timeS;
    expect(gained).toBeCloseTo(expected, 9);
    expect(gained).toBeLessThan(-2); // ~0.01 m² is worth a few seconds over 4 km
    expect(worthSeconds(0.22, { fit, conditions }, scenario)).toBe(0);
  });
});
