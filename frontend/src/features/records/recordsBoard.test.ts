import { describe, expect, it } from "vitest";
import { entryId, groupByPlace, improvements, selectionOf } from "./recordsBoard";
import type { RecordEntry } from "./types";

function entry(over: Partial<RecordEntry>): RecordEntry {
  return {
    place: "Tour complet",
    track_id: "t1",
    event_key: "500m",
    start_type: "standing",
    time_ms: 40_000,
    achieved_on: "2026-07-01",
    source: "sqorz",
    is_competition: false,
    external_event_id: "e1",
    lap_id: "l1",
    manual_result_id: null,
    ...over,
  };
}

describe("groupByPlace", () => {
  it("groups by track, keeping the order entries came in", () => {
    const groups = groupByPlace([
      entry({ event_key: "f200" }),
      entry({ event_key: "lap" }),
      entry({ track_id: "t2", place: "Other" }),
    ]);
    expect(groups.map((g) => [g.place, g.entries.length])).toEqual([
      ["Tour complet", 2],
      ["Other", 1],
    ]);
  });

  it("keeps two tracks with the same name apart, and merges a venue modulo case and spaces", () => {
    const groups = groupByPlace([
      entry({ track_id: "t1" }),
      entry({ track_id: "t9" }),
      entry({ track_id: null, place: "Mont-Royal", source: "manual" }),
      entry({ track_id: null, place: " mont-royal ", source: "manual" }),
    ]);
    expect(groups.map((g) => g.entries.length)).toEqual([1, 1, 2]);
  });

  it("is empty for no records", () => {
    expect(groupByPlace([])).toEqual([]);
  });
});

describe("improvements", () => {
  it("is the change against the previous record", () => {
    const history = [entry({ time_ms: 40_000 }), entry({ time_ms: 39_000 }), entry({ time_ms: 38_500 })];
    expect(improvements(history)).toEqual([null, -1000, -500]);
    expect(improvements([])).toEqual([]);
  });
});

describe("selectionOf / entryId", () => {
  it("asks for the history of a track record by track id", () => {
    expect(selectionOf(entry({}))).toEqual({ track_id: "t1", place: "Tour complet", event_key: "500m", start_type: "standing" });
  });

  it("keeps the venue text for a manual result with no track", () => {
    expect(selectionOf(entry({ track_id: null, place: "Mont-Royal", source: "manual" }))?.track_id).toBeNull();
  });

  it("returns null for combinations that aren't standard records", () => {
    expect(selectionOf(entry({ event_key: "marathon" }))).toBeNull();
    expect(selectionOf(entry({ event_key: "f200", start_type: "standing" }))).toBeNull();
    expect(selectionOf(entry({ start_type: "unknown" }))).toBeNull();
  });

  it("tells records apart by place, event and start type", () => {
    const ids = new Set([
      entryId(entry({})),
      entryId(entry({ start_type: "flying" })),
      entryId(entry({ event_key: "1km" })),
      entryId(entry({ track_id: "t2" })),
    ]);
    expect(ids.size).toBe(4);
  });
});
