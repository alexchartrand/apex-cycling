import { describe, expect, it } from "vitest";
import { compliancePercent, gapToShow, splitSquad } from "./squad";
import type { SquadRow } from "./types";

const row = (over: Partial<SquadRow>): SquadRow => ({
  athlete_id: "a",
  athlete_name: "A",
  rank: 1,
  time_ms: 36000,
  gap_ms: 0,
  achieved_on: "2026-03-01",
  place: "Bromont",
  track_id: "t",
  source: "sqorz",
  ...over,
});

describe("squad helpers", () => {
  it("shows a gap only for someone behind the leader", () => {
    expect(gapToShow(row({ gap_ms: 0 }))).toBeNull();
    expect(gapToShow(row({ gap_ms: 350 }))).toBe(350);
    expect(gapToShow(row({ gap_ms: null, time_ms: null }))).toBeNull();
  });

  it("separates athletes with a time from those without", () => {
    const rows = [row({ athlete_name: "A" }), row({ athlete_name: "B", time_ms: null, rank: null, gap_ms: null })];
    const { ranked, unranked } = splitSquad(rows);
    expect(ranked.map((r) => r.athlete_name)).toEqual(["A"]);
    expect(unranked.map((r) => r.athlete_name)).toEqual(["B"]);
  });

  it("rounds compliance to a whole percentage", () => {
    expect(compliancePercent(0.666)).toBe(67);
    expect(compliancePercent(null)).toBeNull();
  });
});
