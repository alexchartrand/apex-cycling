import { describe, expect, it } from "vitest";
import { groupBySession, improvementMs, newInsights } from "./insights";
import type { Insight } from "./types";

function insight(key: string, session: string, overrides: Partial<Insight> = {}): Insight {
  return {
    key,
    kind: "personal_record",
    external_event_id: session,
    session_name: `Session ${session}`,
    event_date: "2026-04-04",
    track_id: "t1",
    track_name: "Tour complet",
    event_key: "500m",
    start_type: "standing",
    time_ms: 47_535,
    previous_ms: 51_434,
    milestone_ms: null,
    lap_number: null,
    lap_count: null,
    cv_pct: null,
    effort_start_type: null,
    first_lap_id: null,
    ...overrides,
  };
}

describe("groupBySession", () => {
  it("keeps the feed's order and gathers each session's headlines", () => {
    const groups = groupBySession([insight("a", "s2"), insight("b", "s2"), insight("c", "s1")]);
    expect(groups.map((g) => [g.external_event_id, g.insights.map((i) => i.key)])).toEqual([
      ["s2", ["a", "b"]],
      ["s1", ["c"]],
    ]);
    expect(groups[0].session_name).toBe("Session s2");
  });

  it("is empty for an empty feed", () => {
    expect(groupBySession([])).toEqual([]);
  });
});

describe("newInsights", () => {
  it("returns the headlines that weren't there before", () => {
    const before = [insight("a", "s1")];
    const after = [insight("b", "s2"), insight("a", "s1")];
    expect(newInsights(before, after).map((i) => i.key)).toEqual(["b"]);
    expect(newInsights(after, after)).toEqual([]);
  });
});

describe("improvementMs", () => {
  it("is how much faster the new time is", () => {
    expect(improvementMs(insight("a", "s1"))).toBe(3_899);
    expect(improvementMs(insight("a", "s1", { previous_ms: null }))).toBeNull();
  });
});
