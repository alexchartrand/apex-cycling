import { describe, expect, it } from "vitest";
import { loadChange, signed } from "./loadChange";

const week = (sessions: number, laps: number) => ({ sessions, laps, avg_rpe: null });

describe("loadChange", () => {
  it("compares laps and sessions with the week before", () => {
    expect(loadChange(week(3, 120), week(2, 90))).toEqual({ laps: 30, sessions: 1, direction: "up" });
    expect(loadChange(week(1, 40), week(2, 90))).toEqual({ laps: -50, sessions: -1, direction: "down" });
    expect(loadChange(week(2, 90), week(1, 90))).toEqual({ laps: 0, sessions: 1, direction: "same" });
  });

  it("says nothing when neither week had any training", () => {
    expect(loadChange(week(0, 0), week(0, 0)).direction).toBe("none");
  });

  it("still reports a week that dropped to nothing", () => {
    expect(loadChange(week(0, 0), week(2, 80))).toEqual({ laps: -80, sessions: -2, direction: "down" });
  });
});

describe("signed", () => {
  it("uses a real minus sign and ± for zero", () => {
    expect(signed(5)).toBe("+5");
    expect(signed(-5)).toBe("−5");
    expect(signed(0)).toBe("±0");
  });
});
