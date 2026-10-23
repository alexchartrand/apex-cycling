import { describe, expect, it } from "vitest";
import type { Effort, LapDetail, TrackSessionDetail } from "../training/types";
import type { Bike } from "../equipment/types";
import { developmentAt, effortBands, lapSpeeds, recordingClockStart, sessionGearing } from "./sessionOverlay";

// Head unit started at 18:00:00 with its clock 10 s behind sqorz's: sqorz 18:00:10 is its x = 0.
const recording = { start_time: "2026-04-04T18:00:00Z", clock_offset_s: 10, elapsed_s: 3600 };

function effort(index: number, start: string, lapTimes: (number | null)[]): Effort {
  return { index, start_time: start, lap_times_ms: lapTimes, label: null } as Effort;
}

function lap(start: string, ms: number | null, excluded = false): LapDetail {
  return { lap_id: start, start_time: start, whole_lap_time_ms: ms, excluded } as LapDetail;
}

function track(id: string, laps: LapDetail[]): TrackSessionDetail {
  return { track_id: id, track_name: id, laps } as TrackSessionDetail;
}

describe("recordingClockStart", () => {
  it("is the sqorz time of the recording's first sample", () => {
    expect(new Date(recordingClockStart(recording)).toISOString()).toBe("2026-04-04T18:00:10.000Z");
  });
});

describe("effortBands", () => {
  it("places an effort on the recording's clock, shifted by the offset", () => {
    const bands = effortBands([effort(1, "2026-04-04T18:10:10Z", [20_000, 18_500, null])], recording);
    expect(bands).toEqual([{ fromS: 600, toS: 638.5, index: 1, label: null }]);
  });

  it("drops efforts outside the recording", () => {
    const bands = effortBands(
      [effort(1, "2026-04-04T17:50:00Z", [20_000]), effort(2, "2026-04-04T19:30:00Z", [20_000]), effort(3, "2026-04-04T18:20:10Z", [null])],
      recording,
    );
    expect(bands).toEqual([]);
  });
});

describe("lapSpeeds", () => {
  it("gives each lap's speed on the recording's clock, in time order", () => {
    const laps = lapSpeeds(
      [track("t", [lap("2026-04-04T18:20:10Z", 25_000), lap("2026-04-04T18:10:10Z", 20_000), lap("2026-04-04T19:30:00Z", 20_000)])],
      new Map([["t", 250]]),
      recording,
    );
    expect(laps).toEqual([
      { fromS: 600, toS: 620, kmh: 45 },
      { fromS: 1200, toS: 1225, kmh: 36 },
    ]);
  });

  it("needs the track length and skips excluded or unfinished laps", () => {
    const tracks = [track("t", [lap("2026-04-04T18:10:10Z", 20_000, true), lap("2026-04-04T18:10:30Z", null)]), track("u", [lap("2026-04-04T18:11:00Z", 20_000)])];
    expect(lapSpeeds(tracks, new Map([["t", 250]]), recording)).toEqual([]);
  });
});

describe("sessionGearing", () => {
  const bikes = [{ id: "b", gears: [{ id: "g49x14", development_m: 7.336 }, { id: "g50x13", development_m: 8.06 }] }] as Bike[];

  it("takes the session's gear, and an effort's own gear over its span", () => {
    const efforts = [{ ...effort(1, "2026-04-04T18:10:10Z", [20_000]), gear_setup_id: "g50x13" }, effort(2, "2026-04-04T18:20:10Z", [20_000])];
    const gearing = sessionGearing("g49x14", efforts, bikes, recording);
    expect(gearing).toEqual({ sessionDevelopmentM: 7.336, efforts: [{ fromS: 600, toS: 620, developmentM: 8.06 }] });
    expect(developmentAt(gearing, 610)).toBe(8.06);
    expect(developmentAt(gearing, 1210)).toBe(7.336);
  });

  it("knows no gear when the session's isn't one of the bikes' (deleted) or none is set", () => {
    const gearing = sessionGearing("gone", [], bikes, recording);
    expect(gearing).toEqual({ sessionDevelopmentM: null, efforts: [] });
    expect(developmentAt(gearing, 10)).toBeNull();
  });
});
