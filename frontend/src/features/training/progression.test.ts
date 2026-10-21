import { describe, expect, it } from "vitest";
import {
  availableEvents,
  buildProgressionParams,
  defaultStart,
  personalBestLine,
  recordSessions,
  startTypeApplies,
} from "./progression";
import type { ProgressionPoint, TrackSummary } from "./types";

const track = (length_m: number | null): TrackSummary => ({
  id: "t1",
  name: "Tour complet",
  length_m,
  indoor: null,
  elevation_m: null,
  default_temp_c: null,
  sqorz_name: null,
  city: null,
  region: null,
  country: null,
  latitude: null,
  longitude: null,
  width_m: null,
  surface: null,
  bank_straight_deg: null,
  bank_curve_deg: null,
  notes: null,
  can_edit: false,
  loops: [],
  views: [],
});

const base = { distance: "", start: "any" as const, from: "", to: "" };

describe("availableEvents / defaults", () => {
  it("offers whole-lap events only when the track length is known", () => {
    expect(availableEvents(track(null))).toEqual([]);
    expect(availableEvents(undefined)).toEqual([]);
    expect(availableEvents(track(250))).toEqual(["lap", "500m", "750m", "1km", "2km", "3km", "4km"]);
  });

  it("defaults the start type per metric", () => {
    expect(defaultStart("event:lap")).toBe("flying");
    expect(defaultStart("event:4km")).toBe("standing");
    expect(defaultStart("custom_distance")).toBe("any");
    expect(defaultStart("lap_time")).toBe("any");
  });

  it("only applies the start filter to whole-lap distances on a track with a length", () => {
    expect(startTypeApplies("event:1km", track(250))).toBe(true);
    expect(startTypeApplies("custom_distance", track(250))).toBe(true);
    expect(startTypeApplies("custom_distance", track(null))).toBe(false);
    expect(startTypeApplies("lap_time", track(250))).toBe(false);
  });
});

describe("buildProgressionParams", () => {
  it("builds the existing metrics unchanged", () => {
    expect(buildProgressionParams({ ...base, track: track(250), metricKey: "lap_time" })).toEqual({
      metric: "lap_time",
      track_id: "t1",
      from: undefined,
      to: undefined,
    });
    expect(buildProgressionParams({ ...base, track: track(250), metricKey: "view:v9", from: "2026-01-01" })).toEqual({
      metric: "view",
      track_view_id: "v9",
      from: "2026-01-01",
      to: undefined,
    });
  });

  it("needs a positive numeric distance for a custom one", () => {
    const params = (distance: string) => buildProgressionParams({ ...base, track: track(250), metricKey: "custom_distance", distance });
    expect(params("")).toBeNull();
    expect(params("0")).toBeNull();
    expect(params("abc")).toBeNull();
    expect(params("150")).toMatchObject({ metric: "custom_distance", distance_m: 150, start_type: undefined });
  });

  it("maps a standard event to its distance and chosen start type", () => {
    expect(buildProgressionParams({ ...base, track: track(250), metricKey: "event:1km", start: "standing" })).toMatchObject({
      metric: "custom_distance",
      track_id: "t1",
      distance_m: 1000,
      start_type: "standing",
    });
    // "any" sends no start filter.
    expect(buildProgressionParams({ ...base, track: track(250), metricKey: "event:1km" })?.start_type).toBeUndefined();
  });

  it("makes the flying lap one lap of this track", () => {
    expect(buildProgressionParams({ ...base, track: track(333.3), metricKey: "event:lap", start: "flying" })).toMatchObject({
      distance_m: 333.3,
      start_type: "flying",
    });
  });

  it("refuses a standard event on a track with no length, and drops a start filter that can't apply", () => {
    expect(buildProgressionParams({ ...base, track: track(null), metricKey: "event:500m" })).toBeNull();
    expect(buildProgressionParams({ ...base, track: track(null), metricKey: "custom_distance", distance: "500", start: "standing" })?.start_type).toBeUndefined();
    expect(buildProgressionParams({ ...base, track: undefined, metricKey: "lap_time" })).toBeNull();
    expect(buildProgressionParams({ ...base, track: track(250), metricKey: "event:marathon" })).toBeNull();
  });
});

describe("personal best line", () => {
  it("is the running minimum in time order", () => {
    expect(
      personalBestLine([
        { t: 3, timeMs: 38_000 },
        { t: 1, timeMs: 40_000 },
        { t: 2, timeMs: 41_000 },
        { t: 4, timeMs: 37_000 },
      ]),
    ).toEqual([
      { t: 1, pbMs: 40_000 },
      { t: 2, pbMs: 40_000 },
      { t: 3, pbMs: 38_000 },
      { t: 4, pbMs: 37_000 },
    ]);
    expect(personalBestLine([])).toEqual([]);
  });
});

describe("recordSessions", () => {
  const point = (id: string, date: string, ms: number): ProgressionPoint => ({
    external_event_id: id,
    event_date: date,
    best_lap_id: "l",
    time_ms: ms,
    achieved_distance_m: null,
  });

  it("flags sessions that beat everything before them, not ties", () => {
    const ids = recordSessions([point("c", "2026-03-01", 38_000), point("a", "2026-01-01", 40_000), point("b", "2026-02-01", 41_000), point("d", "2026-04-01", 38_000)]);
    expect([...ids].sort()).toEqual(["a", "c"]);
  });
});
