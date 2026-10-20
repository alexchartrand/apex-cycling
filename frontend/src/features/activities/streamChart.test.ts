import { describe, expect, it } from "vitest";
import { availableChannels, canUseDistance, toRows, windowAverage } from "./streamChart";
import type { ActivityStreams } from "./types";

const streams: ActivityStreams = {
  sample_count: 4,
  point_count: 4,
  time_s: [0, 10, 20, 30],
  power_w: [100, 200, null, 400],
  heart_rate: [120, 130, 140, 150],
  cadence: null,
  speed_mps: [5, 10, 10, 5],
  distance_m: [0, 50, 150, 200],
  altitude_m: null,
};

describe("availableChannels", () => {
  it("lists only what the recording carries", () => {
    expect(availableChannels(streams)).toEqual(["power", "heartRate", "speed"]);
  });
});

describe("toRows", () => {
  it("uses time by default and converts speed to km/h", () => {
    const rows = toRows(streams, "time");
    expect(rows.map((r) => r.x)).toEqual([0, 10, 20, 30]);
    expect(rows[1]).toMatchObject({ power: 200, heartRate: 130, cadence: null, speed: 36, altitude: null });
    expect(rows[2].power).toBeNull();
  });

  it("uses kilometres for the distance axis", () => {
    expect(toRows(streams, "distance").map((r) => r.x)).toEqual([0, 0.05, 0.15, 0.2]);
  });

  it("falls back to time when distance can't be an axis", () => {
    const flat = { ...streams, distance_m: null };
    expect(canUseDistance(flat)).toBe(false);
    expect(toRows(flat, "distance").map((r) => r.x)).toEqual([0, 10, 20, 30]);
    expect(canUseDistance({ ...streams, distance_m: [0, 0, 0, 0] })).toBe(false);
  });

  it("skips points without an x value", () => {
    const gappy = { ...streams, time_s: [0, null, 20, 30] };
    expect(toRows(gappy, "time")).toHaveLength(3);
  });
});

describe("windowAverage", () => {
  it("averages the readings inside the window and ignores gaps", () => {
    const rows = toRows(streams, "time");
    expect(windowAverage(rows, "power", 0, 30)).toBeCloseTo((100 + 200 + 400) / 3);
    expect(windowAverage(rows, "power", 10, 20)).toBe(200);
    expect(windowAverage(rows, "cadence", 0, 30)).toBeNull();
    expect(windowAverage(rows, "power", 100, 200)).toBeNull();
  });
});
