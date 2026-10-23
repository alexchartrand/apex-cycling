import { afterEach, describe, expect, it, vi } from "vitest";
import { buildChecklist, dismiss, isDismissed, lapTotals } from "./checklist";

describe("buildChecklist", () => {
  it("starts with nothing done, in the order transponder, weight, club, coach", () => {
    const list = buildChecklist({ transponders: 0, weightKg: null, clubs: 0, activeCoaches: 0 });
    expect(list.steps.map((s) => [s.key, s.done])).toEqual([
      ["transponder", false],
      ["physiology", false],
      ["club", false],
      ["coach", false],
    ]);
    expect(list).toMatchObject({ doneCount: 0, total: 4, complete: false });
  });

  it("counts what is done and sends each step to where it is done", () => {
    const list = buildChecklist({ transponders: 1, weightKg: 72, clubs: 0, activeCoaches: 0 });
    expect(list.doneCount).toBe(2);
    expect(list.steps.map((s) => s.to)).toEqual(["/import#sqorz", "/settings/physiology", "/club", "/coach"]);
    expect(list.steps.filter((s) => s.optional).map((s) => s.key)).toEqual(["club", "coach"]);
  });

  it("is complete when all four are done", () => {
    expect(buildChecklist({ transponders: 2, weightKg: 70.5, clubs: 1, activeCoaches: 1 }).complete).toBe(true);
  });
});

describe("dismissal", () => {
  afterEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("is remembered per athlete", () => {
    expect(isDismissed("a1")).toBe(false);
    dismiss("a1");
    expect(isDismissed("a1")).toBe(true);
    expect(isDismissed("a2")).toBe(false);
  });

  it("doesn't break when storage is blocked", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(isDismissed("a1")).toBe(false);
    expect(() => dismiss("a1")).not.toThrow();
  });
});

describe("lapTotals", () => {
  it("adds laps and counts sessions", () => {
    expect(lapTotals([{ lap_count: 12 }, { lap_count: 30 }])).toEqual({ laps: 42, sessions: 2 });
    expect(lapTotals([])).toEqual({ laps: 0, sessions: 0 });
  });
});
