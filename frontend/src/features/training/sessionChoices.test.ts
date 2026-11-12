import { describe, expect, it } from "vitest";
import { mergeChoices, missingChoices } from "./sessionChoices";
import type { SessionSummary } from "./types";

const session = (id: string, date: string, first: string | null = null) =>
  ({ external_event_id: id, event_date: date, first_lap_at: first }) as SessionSummary;

describe("missingChoices", () => {
  it("lists the selected sessions that aren't loaded, once, ignoring blanks", () => {
    expect(missingChoices([session("a", "2026-06-02")], ["a", "", "old", "old"])).toEqual(["old"]);
  });
});

describe("mergeChoices", () => {
  it("drops repeats (a page shifted by a new session) and keeps the server's order", () => {
    const loaded = [session("b", "2026-06-02"), session("a", "2026-06-01"), session("a", "2026-06-01")];
    expect(mergeChoices(loaded, []).map((s) => s.external_event_id)).toEqual(["b", "a"]);
  });

  it("files an older selected session in date order, same day by first lap", () => {
    const loaded = [session("late", "2026-06-02", "2026-06-02T18:00:00Z"), session("mid", "2026-06-01")];
    const extra = [session("old", "2025-01-01"), session("early", "2026-06-02", "2026-06-02T08:00:00Z")];
    expect(mergeChoices(loaded, extra).map((s) => s.external_event_id)).toEqual(["late", "early", "mid", "old"]);
  });
});
