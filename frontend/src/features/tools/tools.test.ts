import { describe, expect, it } from "vitest";
import { cadenceForLapTime, cadenceTable } from "./gearing";
import { makeSetup, simulate } from "./physics";
import { boardReducer, INITIAL_BOARD, paceOf, tapDeltas } from "./pursuitBoard";
import { effortElapsedByLap, pursuitSchedule } from "./pursuitSchedule";
import { parseNumber, rawValue, readNumberField, readTimeField, shareQuery } from "./toolInputs";
import { sensitivities } from "./whatIf";

const setup = makeSetup({ massKg: 83, cdaM2: 0.22, rho: 1.2 });

describe("tool inputs", () => {
  it("reads numbers typed with either decimal mark", () => {
    expect(parseNumber("0,22")).toBe(0.22);
    expect(parseNumber(" 0.22 ")).toBe(0.22);
    expect(parseNumber("12.")).toBe(12);
    expect(parseNumber("")).toBeNull();
    expect(parseNumber("1e3")).toBeNull();
    expect(parseNumber("abc")).toBeNull();
  });

  it("flags out-of-range, non-integer and missing required values", () => {
    expect(readNumberField("cda", "0.22")).toEqual({ raw: "0.22", value: 0.22, invalid: false });
    expect(readNumberField("cda", "2").invalid).toBe(true);
    expect(readNumberField("cog", "14.5").invalid).toBe(true);
    expect(readNumberField("riderKg", "").invalid).toBe(true);
    // Pressure is optional: blank means "estimate it from the elevation".
    expect(readNumberField("pressureHpa", "")).toEqual({ raw: "", value: null, invalid: false });
    expect(readTimeField("4:15,5").seconds).toBe(255.5);
    expect(readTimeField("4:75").invalid).toBe(true);
  });

  it("prefers the URL, then the profile, then the fallback", () => {
    const params = new URLSearchParams("rider=70");
    expect(rawValue(params, "riderKg", { riderKg: 68 })).toBe("70");
    expect(rawValue(new URLSearchParams(), "riderKg", { riderKg: 68 })).toBe("68");
    expect(rawValue(new URLSearchParams(), "riderKg", {})).toBe("75");
    expect(rawValue(new URLSearchParams(), "pressureHpa", {})).toBe("");
  });

  it("writes a share link with every value in effect", () => {
    expect(shareQuery({ rider: "70", cda: " 0.21 ", hpa: "", track: null })).toBe("rider=70&cda=0.21");
  });
});

describe("pursuit schedule", () => {
  const schedule = pursuitSchedule(4000, 270, 250, setup)!;

  it("has one row per half lap and ends exactly on the target", () => {
    expect(schedule.rows).toHaveLength(32);
    const last = schedule.rows.at(-1)!;
    expect(last).toMatchObject({ halfLap: 32, distanceM: 4000, lap: 16 });
    expect(last.elapsedS).toBeCloseTo(270, 9);
  });

  it("is slow out of the gate, then even", () => {
    const laps = schedule.rows.filter((row) => row.lap !== null).map((row) => row.lapS!);
    expect(laps[0]).toBeGreaterThan(laps[5] + 3);
    expect(laps[10]).toBeCloseTo(laps[15], 2);
    expect(laps.reduce((a, b) => a + b, 0)).toBeCloseTo(270, 9);
    expect(schedule.averagePowerW).toBeGreaterThan(schedule.powerW);
  });

  it("matches the physics at the race power it reports", () => {
    expect(simulate(4000, schedule.powerW, setup)!.timeS).toBeCloseTo(270, 2);
  });

  it("handles a distance that isn't whole half laps (333.33 m track)", () => {
    const rows = pursuitSchedule(2000, 150, 333.33, setup)!.rows;
    expect(rows.at(-1)!.distanceM).toBe(2000);
    expect(rows.at(-1)!.elapsedS).toBeCloseTo(150, 9);
  });

  it("gives up on an impossible target", () => {
    expect(pursuitSchedule(4000, 60, 250, setup)).toBeNull();
  });

  it("chains a ridden effort's laps, stopping at an unfinished one", () => {
    expect(effortElapsedByLap([22_000, 17_500, null, 17_000])).toEqual([22, 39.5]);
  });
});

describe("what-if sensitivities", () => {
  const rows = sensitivities({ setup, distanceM: 4000, powerW: 450, standing: true }, 1.18);
  const byKey = Object.fromEntries(rows.map((row) => [row.key, row]));

  it("signs each change the way physics says", () => {
    expect(byKey.cdaDown.deltaTimeS).toBeLessThan(0);
    expect(byKey.cdaUp.deltaTimeS).toBeGreaterThan(0);
    expect(byKey.massDown.deltaTimeS).toBeLessThan(0);
    expect(byKey.powerUp.deltaTimeS).toBeLessThan(0);
    expect(byKey.crrDown.deltaTimeS).toBeLessThan(0);
    expect(byKey.warmer.deltaTimeS).toBeLessThan(0);
    expect(byKey.cdaDown.deltaPowerW).toBeLessThan(0);
    expect(byKey.powerUp.deltaPowerW).toBe(10);
  });

  it("puts −0.01 CdA at a few seconds over 4 km, worth roughly 20 W", () => {
    expect(byKey.cdaDown.deltaTimeS).toBeLessThan(-3);
    expect(byKey.cdaDown.deltaTimeS).toBeGreaterThan(-6);
    expect(byKey.cdaDown.deltaPowerW).toBeLessThan(-15);
    expect(byKey.cdaDown.deltaPowerW).toBeGreaterThan(-25);
  });
});

describe("gearing", () => {
  it("builds the cadence table", () => {
    const [row] = cadenceTable(52, 14, 2.1, 250, [110]);
    expect(row.speedKmh).toBeCloseTo(7.8 * 110 / 60 * 3.6, 9);
    expect(row.lapS).toBeCloseTo(250 / (7.8 * 110 / 60), 9);
    expect(row.flying200S).toBeCloseTo(200 / (7.8 * 110 / 60), 9);
  });

  it("inverts a lap time into a cadence", () => {
    const [row] = cadenceTable(52, 14, 2.1, 250, [117]);
    expect(cadenceForLapTime(row.lapS, 250, 52, 14, 2.1)).toBeCloseTo(117, 9);
  });
});

describe("trackside board", () => {
  it("compares each tap with the schedule", () => {
    let state = boardReducer(INITIAL_BOARD, { type: "tap", at: 500 });
    expect(state).toBe(INITIAL_BOARD); // no tap before the start
    state = boardReducer(state, { type: "start", at: 1_000 });
    state = boardReducer(state, { type: "tap", at: 13_200 });
    state = boardReducer(state, { type: "tap", at: 21_000 });
    state = boardReducer(state, { type: "tap", at: 29_000 });
    state = boardReducer(state, { type: "undo" });
    const deltas = tapDeltas(state, [12, 20.1, 28.5]);
    expect(deltas).toHaveLength(2);
    expect(deltas[0]).toBeCloseTo(0.2, 9);
    expect(deltas[1]).toBeCloseTo(-0.1, 9);
    expect(boardReducer(state, { type: "start", at: 99 })).toBe(state); // already running
    expect(boardReducer(state, { type: "reset" })).toEqual(INITIAL_BOARD);
  });

  it("calls the pace with a small dead band", () => {
    expect(paceOf(-0.3)).toBe("ahead");
    expect(paceOf(0.1)).toBe("onPace");
    expect(paceOf(0.4)).toBe("behind");
  });
});
