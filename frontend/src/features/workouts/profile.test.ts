import { describe, expect, it } from "vitest";
import { clockText, lengthText, profileBars, profileScale, timeTicks, UNRATED_INTENSITY } from "./profile";
import type { ProfileSegment } from "./types";

const segment = (overrides: Partial<ProfileSegment>): ProfileSegment => ({
  start_s: 0,
  duration_s: 60,
  kind: "work",
  label: null,
  intensity: null,
  power_low: null,
  power_high: null,
  is_track: false,
  ...overrides,
});

describe("profileScale", () => {
  it("leaves room above FTP, and above the hardest step up to a cap", () => {
    expect(profileScale([segment({ intensity: 0.6 })])).toBe(1.2);
    expect(profileScale([segment({ intensity: 1.5 })])).toBe(1.7);
    expect(profileScale([segment({ intensity: 1.0, power_low: 1.0, power_high: 1.6 })])).toBe(1.8);
    expect(profileScale([segment({ intensity: 3 })])).toBe(2.5);
  });
});

describe("profileBars", () => {
  it("places bars along the workout and colours them by kind", () => {
    const bars = profileBars(
      [
        segment({ kind: "warmup", duration_s: 600, intensity: 0.6 }),
        segment({ start_s: 600, duration_s: 300, intensity: 1.2, is_track: true }),
        segment({ start_s: 900, duration_s: 300, kind: "recovery" }),
      ],
      1.5,
    );
    expect(bars.map((bar) => [bar.x, bar.width, bar.tone, bar.unrated])).toEqual([
      [0, 0.5, "easy", false],
      [0.5, 0.25, "track", false],
      [0.75, 0.25, "recovery", true],
    ]);
    expect(bars[0].height).toBeCloseTo(0.4);
    expect(bars[2].height).toBeCloseTo(UNRATED_INTENSITY / 1.5);
  });

  it("draws a power range up to its top, with its bottom marked", () => {
    const [bar] = profileBars([segment({ intensity: 0.9, power_low: 0.8, power_high: 1.0 })], 2);
    expect(bar.height).toBeCloseTo(0.5);
    expect(bar.rangeLow).toBeCloseTo(0.4);
  });

  it("clips above the scale and has nothing to draw without time", () => {
    expect(profileBars([segment({ intensity: 4 })], 2.5)[0].height).toBe(1);
    expect(profileBars([])).toEqual([]);
  });
});

describe("timeTicks", () => {
  it("picks a round step that fits", () => {
    expect(timeTicks(3600)).toEqual([0, 900, 1800, 2700, 3600]);
    expect(timeTicks(240)).toEqual([0, 60, 120, 180, 240]);
    expect(timeTicks(5 * 3600)).toEqual([0, 3600, 7200, 10800, 14400, 18000]);
    expect(timeTicks(0)).toEqual([]);
  });
});

describe("time text", () => {
  it("spells out hours so 1:20 can't mean 80 minutes", () => {
    expect([8, 1200, 4800, 3725].map(clockText)).toEqual(["0:08", "20:00", "1:20:00", "1:02:05"]);
    expect([2700, 3600, 3900, 5520].map(lengthText)).toEqual(["45 min", "1 h", "1 h 05", "1 h 32"]);
  });
});
