import { describe, expect, it } from "vitest";
import { addDays, dayBounds } from "./dayRange";

describe("addDays", () => {
  it("crosses months and years", () => {
    expect(addDays("2026-01-31", 1)).toBe("2026-02-01");
    expect(addDays("2026-01-01", -1)).toBe("2025-12-31");
  });
});

describe("dayBounds", () => {
  it("runs from the first day's local midnight to the midnight after the last", () => {
    const { start, end } = dayBounds("2026-03-01", "2026-03-31");
    expect(new Date(start).getTime()).toBe(new Date(2026, 2, 1).getTime());
    expect(new Date(end).getTime()).toBe(new Date(2026, 3, 1).getTime());
  });
});
