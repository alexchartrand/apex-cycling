import { describe, expect, it } from "vitest";
import {
  bestLap,
  distanceRiddenM,
  flying200Ms,
  groupByMonth,
  lapNumber,
  ridingTimeMs,
  startOfWeek,
  summarizeWeek,
  topSpeedKmh,
} from "./sessionStats";
import type { LapDetail, SessionSummary } from "./types";

function lap(
  id: string,
  ms: number | null,
  f200: number | null = null,
  startNumber: number | null = null,
  excluded = false,
): LapDetail {
  return {
    lap_id: id,
    start_time: "2026-10-17T14:00:00Z",
    class_code: null,
    start_number: startNumber,
    whole_lap_time_ms: ms,
    excluded,
    label: null,
    segments: [],
    views: f200 == null ? [] : [{ track_view_id: "v", name: "200m", time_ms: f200 }],
  };
}

function session(date: string, laps: number, first?: string, last?: string): SessionSummary {
  return {
    external_event_id: date,
    event_name: `Session ${date}`,
    event_date: date,
    lap_count: laps,
    track_names: ["Tour complet"],
    rpe: null,
    tags: [],
    first_lap_at: first ?? null,
    last_lap_at: last ?? null,
  };
}

describe("bestLap", () => {
  it("finds the lowest value, skipping missing ones", () => {
    const laps = [lap("a", 18_400), lap("b", null), lap("c", 17_900), lap("d", 17_900)];
    expect(bestLap(laps, (l) => l.whole_lap_time_ms)).toMatchObject({ index: 2, value: 17_900 });
  });

  it("returns null when nothing has a value", () => {
    expect(bestLap([lap("a", null)], (l) => l.whole_lap_time_ms)).toBeNull();
  });

  it("works on flying-200 view times", () => {
    const laps = [lap("a", 18_000, 11_900), lap("b", 18_100, 11_482)];
    expect(bestLap(laps, flying200Ms)?.lap.lap_id).toBe("b");
  });
});

describe("bestLap and excluded laps", () => {
  it("never counts an excluded lap, but keeps positions", () => {
    const laps = [lap("a", 18_400), lap("b", 15_000, 9_000, null, true), lap("c", 17_900)];
    expect(bestLap(laps, (l) => l.whole_lap_time_ms)).toMatchObject({ index: 2, value: 17_900 });
    expect(bestLap(laps, flying200Ms)).toBeNull();
  });
});

describe("session totals", () => {
  const laps = [lap("a", 25_000), lap("b", 24_000), lap("c", null), lap("d", 26_000, null, null, true)];

  it("counts distance over finished laps only", () => {
    expect(distanceRiddenM(laps, 250)).toBe(750); // a, b and d finished; c was abandoned
    expect(distanceRiddenM(laps, null)).toBeNull();
    expect(distanceRiddenM([], 250)).toBe(0);
  });

  it("sums riding time over finished laps, excluded or not", () => {
    expect(ridingTimeMs(laps)).toBe(75_000);
    expect(ridingTimeMs([lap("c", null)])).toBe(0);
  });

  it("top speed is the better of the fastest lap and the flying 200", () => {
    // 250 m in 24 s = 37.5 km/h; 200 m in 12 s = 60 km/h.
    expect(topSpeedKmh([lap("a", 24_000, 12_000)], 250)).toBeCloseTo(60);
    // A slower F200 than the lap pace doesn't lower it: 250 m in 15 s = 60 km/h vs 200 m in 13 s = 55.4.
    expect(topSpeedKmh([lap("a", 15_000, 13_000)], 250)).toBeCloseTo(60);
  });

  it("falls back to whatever can be computed, and ignores excluded laps", () => {
    expect(topSpeedKmh([lap("a", 24_000)], 250)).toBeCloseTo(37.5);
    expect(topSpeedKmh([lap("a", 24_000)], null)).toBeNull(); // no lap length, no flying 200
    expect(topSpeedKmh([lap("a", 24_000, 12_000)], null)).toBeCloseTo(60); // the 200 m is known without it
    expect(topSpeedKmh([lap("a", 24_000, 12_000, null, true)], 250)).toBeNull();
    expect(topSpeedKmh([], 250)).toBeNull();
  });
});

describe("lapNumber", () => {
  it("prefers the sqorz start number", () => {
    expect(lapNumber(lap("a", 1, null, 7), 0)).toBe(7);
    expect(lapNumber(lap("a", 1), 4)).toBe(5);
  });
});

describe("weeks", () => {
  it("starts weeks on Monday", () => {
    const sunday = new Date(2026, 9, 18);
    expect(startOfWeek(sunday)).toEqual(new Date(2026, 9, 12));
    expect(startOfWeek(new Date(2026, 9, 19, 23))).toEqual(new Date(2026, 9, 19));
  });

  it("summarizes only sessions inside the week", () => {
    const sessions = [
      session("2026-10-19", 30, "2026-10-19T18:00:00Z", "2026-10-19T19:30:00Z"),
      session("2026-10-17", 40, "2026-10-17T14:00:00Z", "2026-10-17T15:00:00Z"),
      session("2026-10-12", 20),
      session("2026-10-11", 99),
    ];
    expect(summarizeWeek(sessions, new Date(2026, 9, 12))).toEqual({ sessions: 2, laps: 60, trackSeconds: 3600 });
  });
});

describe("groupByMonth", () => {
  it("groups consecutive sessions by month", () => {
    const groups = groupByMonth([session("2026-10-19", 1), session("2026-10-02", 1), session("2026-09-30", 1)]);
    expect(groups.map((g) => [g.month, g.sessions.length])).toEqual([
      ["2026-10", 2],
      ["2026-09", 1],
    ]);
  });
});
