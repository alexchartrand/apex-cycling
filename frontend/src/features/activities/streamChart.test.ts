import { describe, expect, it } from "vitest";
import { availableChannels, canUseDistance, spanIndexes, toRows, windowAverage, withEstimatedCadence, withLapSpeed, withOverlayChannels } from "./streamChart";
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

describe("withLapSpeed", () => {
  it("gives each sample the speed of the lap it falls in, null between laps", () => {
    const rows = withLapSpeed(toRows(streams, "time"), [
      { fromS: 5, toS: 12, kmh: 45 },
      { fromS: 25, toS: 40, kmh: 36 },
    ]);
    expect(rows.map((r) => r.sqorzSpeed)).toEqual([null, 45, null, 36]);
  });
});

describe("withOverlayChannels", () => {
  it("adds the channels only the overlay fills, in their place", () => {
    expect(withOverlayChannels(["power", "altitude"], ["speed"])).toEqual(["power", "speed", "altitude"]);
    expect(withOverlayChannels(["power", "speed"], ["speed", "cadence"])).toEqual(["power", "cadence", "speed"]);
    expect(withOverlayChannels(["power"], [])).toEqual(["power"]);
  });
});

describe("withEstimatedCadence", () => {
  it("turns the recorded speed into rpm with the gear in force, an effort's own gear first", () => {
    // 49×14 on a 2096 mm rollout: 7.336 m per crank turn.
    const rows = withEstimatedCadence(toRows(streams, "time"), {
      sessionDevelopmentM: 7.336,
      efforts: [{ fromS: 15, toS: 25, developmentM: 8 }],
    });
    expect(rows.map((r) => r.estCadence)).toEqual([(5 / 7.336) * 60, (10 / 7.336) * 60, (10 / 8) * 60, (5 / 7.336) * 60].map((v) => expect.closeTo(v, 6)));
  });

  it("is null without a gear or a speed reading", () => {
    const rows = withEstimatedCadence(toRows({ ...streams, speed_mps: [5, null, 5, 5] }, "time"), {
      sessionDevelopmentM: null,
      efforts: [{ fromS: 0, toS: 15, developmentM: 8 }],
    });
    expect(rows.map((r) => r.estCadence)).toEqual([expect.closeTo(37.5, 6), null, null, null]);
  });
});

describe("spanIndexes", () => {
  const rows = toRows({ ...streams, point_count: 4, time_s: [0, 100, 200, 300] }, "time");

  it("frames the session's efforts and laps with a margin", () => {
    expect(spanIndexes(rows, { bands: [{ fromS: 110, toS: 150, index: 1, label: null }], laps: [] }, 20)).toEqual([1, 1]);
    expect(spanIndexes(rows, { bands: [], laps: [{ fromS: 150, toS: 190, kmh: 40 }] }, 60)).toEqual([1, 2]);
  });

  it("is null when the session covers the whole recording or there is nothing to frame", () => {
    expect(spanIndexes(rows, { bands: [{ fromS: 0, toS: 300, index: 1, label: null }], laps: [] }, 0)).toBeNull();
    expect(spanIndexes(rows, { bands: [], laps: [] })).toBeNull();
  });
});
