import { describe, expect, it } from "vitest";
import { addedPhase, draftErrors, draftPayload, emptyDraft, parseHours, withRace, type PlanDraft } from "./planDraft";

const draft = (over: Partial<PlanDraft> = {}): PlanDraft => ({ ...emptyDraft("2027-01-06"), name: "Kilo", ...over });

describe("emptyDraft", () => {
  it("starts on the next Monday and lasts twelve weeks", () => {
    const empty = emptyDraft("2027-01-06"); // a Wednesday
    expect(empty.start).toBe("2027-01-11");
    expect(empty.end).toBe("2027-04-04");
    expect(emptyDraft("2027-01-11").start).toBe("2027-01-11");
  });
});

describe("draftErrors", () => {
  it("needs a name and dates in order, within a year", () => {
    expect(draftErrors(draft({ name: " " })).name).toBe(true);
    expect(draftErrors(draft({ end: "2027-01-01" })).dates).toBe(true);
    expect(draftErrors(draft({ end: "2028-03-01" })).dates).toBe(true);
    expect(draftErrors(draft({ goalDate: "2027-06-01" })).goalDate).toBe(true);
    expect(draftErrors(draft())).toEqual({});
  });
  it("checks the phases", () => {
    const phase = { kind: "base" as const, name: "", focus: "", hours: "" };
    expect(draftErrors(draft({ phases: [{ ...phase, start: "2027-01-01", end: "2027-01-20" }] })).phases).toBe("phaseOutside");
  });
});

describe("draftPayload", () => {
  it("trims, parses decimal commas, sorts phases and drops a time goal from a road plan", () => {
    const payload = draftPayload(
      draft({
        goalText: "  Gran fondo  ",
        hours: "6,5",
        goalId: "g1",
        phases: [
          { kind: "build", name: "", start: "2027-02-01", end: "2027-04-04", focus: " ", hours: "8" },
          { kind: "base", name: " Volume ", start: "2027-01-11", end: "2027-01-31", focus: "", hours: "" },
        ],
      }),
    );
    expect(payload).toMatchObject({ name: "Kilo", goal_text: "Gran fondo", hours_per_week: 6.5, goal_id: null, competition_id: null });
    expect(payload?.phases.map((p) => [p.kind, p.name, p.hours, p.focus])).toEqual([
      ["base", "Volume", null, null],
      ["build", null, 8, null],
    ]);
    expect(draftPayload(draft({ sport: "track_cycling", goalId: "g1" }))?.goal_id).toBe("g1");
    expect(draftPayload(draft({ name: "" }))).toBeNull();
  });
});

describe("withRace", () => {
  it("ends the plan on race day and moves an unset goal date there", () => {
    const next = withRace(draft(), "r1", "2027-05-01");
    expect([next.raceId, next.end, next.goalDate]).toEqual(["r1", "2027-05-01", "2027-05-01"]);
    expect(withRace(draft({ goalDate: "2027-03-01" }), "r1", "2027-05-01").goalDate).toBe("2027-03-01");
    expect(withRace(draft(), "", null).raceId).toBe("");
  });
});

describe("addedPhase and parseHours", () => {
  it("adds a week after the last phase", () => {
    const phase = addedPhase(draft({ phases: [{ kind: "base", name: "", start: "2027-01-11", end: "2027-01-31", focus: "", hours: "" }] }));
    expect([phase.start, phase.end]).toEqual(["2027-02-01", "2027-02-07"]);
    expect(addedPhase(draft()).start).toBe("2027-01-11");
  });
  it("reads hours", () => {
    expect(parseHours(" ")).toBeNull();
    expect(parseHours("7,5")).toBe(7.5);
    expect(Number.isNaN(parseHours("abc"))).toBe(true);
  });
});
