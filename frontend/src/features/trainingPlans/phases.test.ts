import { describe, expect, it } from "vitest";
import { addDays, daysBetween, defaultPlanFor, elapsedShare, phaseProblem, timeline } from "./phases";
import type { Phase, TrainingPlan } from "./types";

const phase = (kind: Phase["kind"], start: string, end: string): Phase => ({ kind, start, end });

describe("dates", () => {
  it("counts whole days across a DST change", () => {
    expect(daysBetween("2027-03-01", "2027-04-01")).toBe(31);
    expect(addDays("2027-03-13", 2)).toBe("2027-03-15");
  });
});

describe("timeline", () => {
  it("lays the phases, today and the race on the plan's span", () => {
    // 28 days from a Wednesday.
    const layout = timeline("2027-01-06", "2027-02-02", [phase("base", "2027-01-06", "2027-01-19"), phase("build", "2027-01-20", "2027-02-02")], "2027-01-06", "2027-02-02");
    expect(layout.days).toBe(28);
    expect(layout.blocks.map((b) => [b.left, b.width])).toEqual([
      [0, 50],
      [50, 50],
    ]);
    expect(layout.today).toBeCloseTo((0.5 / 28) * 100);
    expect(layout.race).toBeCloseTo((27.5 / 28) * 100);
    // The first Monday is the 11th.
    expect(layout.weeks.map((w) => w.day)).toEqual(["2027-01-11", "2027-01-18", "2027-01-25", "2027-02-01"]);
    expect(timeline("2027-01-06", "2027-02-02", [], "2027-03-01").today).toBeNull();
  });
});

describe("phaseProblem", () => {
  const start = "2027-01-01";
  const end = "2027-03-01";
  it("accepts ordered phases inside the plan", () => {
    expect(phaseProblem(start, end, [phase("build", "2027-02-01", "2027-03-01"), phase("base", start, "2027-01-31")])).toBeNull();
  });
  it("names the first problem", () => {
    expect(phaseProblem(start, end, [phase("base", "2027-01-10", "2027-01-05")])).toBe("phaseOrder");
    expect(phaseProblem(start, end, [phase("base", "2026-12-25", "2027-01-05")])).toBe("phaseOutside");
    expect(phaseProblem(start, end, [phase("base", start, "2027-01-20"), phase("build", "2027-01-20", end)])).toBe("phaseOverlap");
  });
});

describe("defaultPlanFor", () => {
  const plan = (id: string, start_date: string, end_date: string) => ({ id, start_date, end_date }) as TrainingPlan;
  it("picks the only plan covering the day", () => {
    const plans = [plan("a", "2027-01-01", "2027-02-01"), plan("b", "2027-01-20", "2027-03-01")];
    expect(defaultPlanFor(plans, "2027-01-05")).toBe("a");
    expect(defaultPlanFor(plans, "2027-01-25")).toBeNull(); // both: let the person choose
    expect(defaultPlanFor(plans, "2027-04-01")).toBeNull();
  });
});

describe("elapsedShare", () => {
  it("is clamped to the plan", () => {
    expect(elapsedShare("2027-01-01", "2027-01-10", "2026-12-01")).toBe(0);
    expect(elapsedShare("2027-01-01", "2027-01-10", "2027-01-05")).toBe(0.5);
    expect(elapsedShare("2027-01-01", "2027-01-10", "2027-02-01")).toBe(1);
  });
});
