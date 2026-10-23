import { describe, expect, it } from "vitest";
import {
  competitionFormErrors,
  competitionPayload,
  defaultSeasonForm,
  emptyCompetitionForm,
  improvementMs,
  nextCompetition,
  seasonPayload,
} from "./season";
import type { Competition } from "./types";

const race = (over: Partial<Competition>): Competition => ({
  id: "c",
  name: "Nationals",
  competition_date: "2026-07-20",
  priority: "A",
  location: null,
  notes: null,
  goal: null,
  days_until: 10,
  taper_starts_on: "2026-07-10",
  days_to_taper: 3,
  phase: "build",
  race_session_id: null,
  ...over,
});

describe("competition form", () => {
  it("needs a name and a date", () => {
    expect(competitionFormErrors(emptyCompetitionForm())).toEqual({ name: true, date: true });
    expect(competitionPayload(emptyCompetitionForm())).toBeNull();
  });

  it("trims text and turns blanks into nulls", () => {
    const payload = competitionPayload({ ...emptyCompetitionForm(), name: " Nationals ", date: "2026-07-20", location: " ", goalId: "g1" });
    expect(payload).toEqual({
      name: "Nationals",
      competition_date: "2026-07-20",
      priority: "B",
      location: null,
      notes: null,
      goal_id: "g1",
    });
  });
});

describe("season form", () => {
  it("defaults to the calendar year", () => {
    expect(defaultSeasonForm("2026-10-23")).toEqual({ name: "2026", start: "2026-01-01" });
  });

  it("rejects a blank name or a bad date", () => {
    expect(seasonPayload({ name: " ", start: "2026-01-01" })).toBeNull();
    expect(seasonPayload({ name: "2026", start: "01/01/2026" })).toBeNull();
    expect(seasonPayload({ name: " 2026 ", start: "2026-01-01" })).toEqual({ name: "2026", start_date: "2026-01-01" });
  });
});

describe("race helpers", () => {
  it("picks the first race still ahead", () => {
    const list = [race({ id: "past", days_until: -3 }), race({ id: "soon", days_until: 4 }), race({ id: "later", days_until: 30 })];
    expect(nextCompetition(list)?.id).toBe("soon");
    expect(nextCompetition([race({ days_until: -1 })])).toBeNull();
  });

  it("measures how much a season best beat the earlier best", () => {
    expect(improvementMs({ time_ms: 35000, previous_best_ms: 36200 })).toBe(1200);
    expect(improvementMs({ time_ms: 35000, previous_best_ms: null })).toBeNull();
  });
});
