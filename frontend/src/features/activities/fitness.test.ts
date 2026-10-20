import { describe, expect, it } from "vitest";
import { formState, loadChartRows, summarizeLoad } from "./fitness";
import type { TrainingLoadDay } from "./types";

const day = (n: number, ctl: number, atl: number, tsb = 0): TrainingLoadDay => ({ day: `2026-06-${String(n).padStart(2, "0")}`, tss: 50, ctl, atl, tsb });

describe("formState", () => {
  it("bands form by TSB", () => {
    expect(formState(12)).toBe("fresh");
    expect(formState(5)).toBe("fresh");
    expect(formState(0)).toBe("balanced");
    expect(formState(-10)).toBe("balanced");
    expect(formState(-11)).toBe("loaded");
    expect(formState(-30)).toBe("loaded");
    expect(formState(-31)).toBe("overreaching");
  });
});

describe("summarizeLoad", () => {
  it("is null without data", () => {
    expect(summarizeLoad([])).toBeNull();
  });

  it("reports today's numbers and the week's change in fitness", () => {
    const days = Array.from({ length: 10 }, (_, i) => day(i + 1, 40 + i, 50, -8));
    const summary = summarizeLoad(days);
    expect(summary).toMatchObject({ ctl: 49, atl: 50, tsb: -8, state: "balanced" });
    expect(summary?.ctlWeekChange).toBeCloseTo(7); // day 10 (49) vs day 3 (42)
  });

  it("copes with less than a week of history", () => {
    expect(summarizeLoad([day(1, 10, 20), day(2, 12, 25)])?.ctlWeekChange).toBeCloseTo(2);
  });
});

describe("loadChartRows", () => {
  it("puts days on a local-midnight time axis", () => {
    const [row] = loadChartRows([day(5, 30, 40, -3)]);
    expect(row.t).toBe(new Date(2026, 5, 5).getTime());
    expect(row).toMatchObject({ ctl: 30, atl: 40, tsb: -3 });
  });
});
