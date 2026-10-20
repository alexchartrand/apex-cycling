import { describe, expect, it } from "vitest";
import { durationLabel, localDay, mpsToKmh } from "./format";

describe("durationLabel", () => {
  it("speaks the way riders do", () => {
    expect(durationLabel(1)).toBe("1 s");
    expect(durationLabel(45)).toBe("45 s");
    expect(durationLabel(60)).toBe("1 min");
    expect(durationLabel(90)).toBe("1:30");
    expect(durationLabel(1200)).toBe("20 min");
    expect(durationLabel(3600)).toBe("1 h");
    expect(durationLabel(5400)).toBe("1 h 30");
  });
});

describe("misc", () => {
  it("converts speed", () => {
    expect(mpsToKmh(10)).toBeCloseTo(36);
    expect(mpsToKmh(null)).toBeNull();
  });

  it("takes the local calendar day of an instant", () => {
    const noon = new Date(2026, 5, 7, 12, 0).toISOString();
    expect(localDay(noon)).toBe("2026-06-07");
  });
});
