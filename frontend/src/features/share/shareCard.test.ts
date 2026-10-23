import { describe, expect, it, vi } from "vitest";
import { createFormatters } from "../../i18n/format";
import type { RecordEntry } from "../records/types";
import type { Effort, LapDetail } from "../training/types";
import { effortCardModel, recordCardModel, type CardTexts } from "./cardModels";
import { CARD_HEIGHT, CARD_WIDTH, drawShareCard, eventLapCount, shareFileName, splitBarHeights, windowSplits, type ShareCardModel } from "./shareCard";

const fmt = createFormatters("en");

function lap(id: string, startMinute: number, ms: number | null): LapDetail {
  return {
    lap_id: id,
    start_time: `2026-04-04T10:${String(startMinute).padStart(2, "0")}:00Z`,
    class_code: null,
    start_number: null,
    whole_lap_time_ms: ms,
    excluded: false,
    label: null,
    segments: [],
    views: [],
  };
}

const texts: CardTexts = { brand: "ApexCycling", eyebrow: "Record · Standing start", title: "500 m", splitsCaption: "Lap times (s)", deltaNote: "vs previous best" };

describe("eventLapCount", () => {
  it("is whole laps of the track, one for a lap and none for the view-timed 200", () => {
    expect(eventLapCount("500m", 250)).toBe(2);
    expect(eventLapCount("4km", 250)).toBe(16);
    expect(eventLapCount("lap", 333.33)).toBe(1);
    expect(eventLapCount("f200", 250)).toBe(0);
    expect(eventLapCount("500m", null)).toBe(0);
    expect(eventLapCount("750m", 400)).toBe(0); // not a whole number of laps
  });
});

describe("windowSplits", () => {
  const laps = [lap("c", 2, 25_000), lap("a", 0, 30_000), lap("b", 1, 24_000)];

  it("takes the laps from the first one in time order", () => {
    expect(windowSplits(laps, "a", 2)).toEqual([
      { label: "1", ms: 30_000 },
      { label: "2", ms: 24_000 },
    ]);
  });

  it("is empty when the run is cut short, has a hole, or the lap is unknown", () => {
    expect(windowSplits(laps, "c", 2)).toEqual([]);
    expect(windowSplits([lap("a", 0, 30_000), lap("b", 1, null)], "a", 2)).toEqual([]);
    expect(windowSplits(laps, "zzz", 2)).toEqual([]);
    expect(windowSplits(laps, null, 2)).toEqual([]);
    expect(windowSplits(laps, "a", 0)).toEqual([]);
  });
});

describe("splitBarHeights", () => {
  it("scales the slowest lap to the full height and the fastest to the floor", () => {
    const heights = splitBarHeights([{ label: "1", ms: 30_000 }, { label: "2", ms: 24_000 }, { label: "3", ms: 27_000 }], 100, 40);
    expect(heights[0]).toBe(100);
    expect(heights[1]).toBe(40);
    expect(heights[2]).toBeCloseTo(70);
  });

  it("draws equal laps equally tall and handles no laps", () => {
    expect(splitBarHeights([{ label: "1", ms: 25_000 }, { label: "2", ms: 25_000 }], 100)).toEqual([100, 100]);
    expect(splitBarHeights([], 100)).toEqual([]);
  });
});

describe("shareFileName", () => {
  it("is a lowercase ascii slug of the title and date", () => {
    expect(shareFileName({ title: "Poursuite 2 km", date: "4 avril 2026" })).toBe("apex-poursuite-2-km-4-avril-2026.png");
    expect(shareFileName({ title: "200 m lancé", date: "x" })).toBe("apex-200-m-lance-x.png");
    expect(shareFileName({ title: "", date: "" })).toBe("apex-card.png");
  });
});

describe("recordCardModel", () => {
  const record: RecordEntry = {
    place: "Bromont",
    track_id: "t1",
    event_key: "500m",
    start_type: "standing",
    time_ms: 47_535,
    achieved_on: "2026-04-04",
    source: "sqorz",
    is_competition: false,
    manual_result_id: null,
    external_event_id: "e1",
    lap_id: "a",
  };

  it("formats the time, the gain over the previous best and the lap splits", () => {
    const model = recordCardModel({ record, laps: [lap("a", 0, 30_000), lap("b", 1, 17_535)], trackLengthM: 250, previousMs: 51_434 }, texts, fmt);
    expect(model.time).toBe("47.535 s");
    expect(model.delta).toBe("−3.899 s");
    expect(model.splits.map((s) => s.ms)).toEqual([30_000, 17_535]);
    expect(model.place).toBe("Bromont");
    expect(model.trackLengthM).toBe(250);
  });

  it("has no delta without a slower previous best", () => {
    expect(recordCardModel({ record, laps: [], trackLengthM: null, previousMs: null }, texts, fmt).delta).toBeNull();
    expect(recordCardModel({ record, laps: [], trackLengthM: null, previousMs: 40_000 }, texts, fmt).delta).toBeNull();
  });

  it("writes long times as m:ss.mmm", () => {
    expect(recordCardModel({ record: { ...record, time_ms: 72_345 }, laps: [], trackLengthM: null, previousMs: null }, texts, fmt).time).toBe("1:12.345");
  });
});

describe("effortCardModel", () => {
  it("shows the total and every finished lap", () => {
    const effort = {
      track_name: "Bromont",
      total_time_ms: 79_000,
      lap_times_ms: [30_000, 25_000, null, 24_000],
    } as Effort;
    const model = effortCardModel({ effort, date: "2026-04-04", trackLengthM: 250 }, texts, fmt);
    expect(model.time).toBe("1:19.000");
    expect(model.splits.map((s) => s.label)).toEqual(["1", "2", "4"]);
    expect(model.delta).toBeNull();
  });
});

describe("drawShareCard", () => {
  function fakeContext() {
    const texts: string[] = [];
    const state: Record<string, unknown> = {};
    const ctx = new Proxy(state, {
      get(target, prop: string) {
        if (prop === "fillText") return (text: string) => texts.push(text);
        if (prop === "measureText") return (text: string) => ({ width: text.length * 10 });
        if (prop in target) return target[prop];
        return vi.fn();
      },
      set(target, prop: string, value) {
        target[prop] = value;
        return true;
      },
    });
    return { ctx: ctx as unknown as CanvasRenderingContext2D, texts };
  }

  const model: ShareCardModel = {
    brand: "ApexCycling",
    eyebrow: "Record · Standing start",
    title: "500 m",
    time: "47.535 s",
    delta: "−3.899 s",
    deltaNote: "vs previous best",
    place: "Bromont",
    date: "April 4, 2026",
    splitsCaption: "Lap times (s)",
    splits: [
      { label: "1", ms: 30_000 },
      { label: "2", ms: 17_535 },
    ],
    trackLengthM: 250,
  };

  it("writes the headline numbers and the splits", () => {
    const { ctx, texts } = fakeContext();
    drawShareCard(ctx, model);
    expect(texts).toEqual(expect.arrayContaining(["APEXCYCLING", "500 m", "47.535 s", "−3.899 s", "vs previous best", "Bromont", "30.0", "17.5"]));
    expect(texts).toContain("RECORD · STANDING START");
    expect(texts).toContain("LAP TIMES (S)");
  });

  it("skips the track and the splits when there are none", () => {
    const { ctx, texts } = fakeContext();
    drawShareCard(ctx, { ...model, splits: [], trackLengthM: null, delta: null, deltaNote: null });
    expect(texts).not.toContain("LAP TIMES (S)");
    expect(texts).toContain("47.535 s");
  });

  it("is a portrait card", () => {
    expect(CARD_WIDTH / CARD_HEIGHT).toBeLessThan(1);
  });
});
