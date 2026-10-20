import { describe, expect, it } from "vitest";
import { changePercent, compareCurves, headlinePowers, rangeBounds } from "./powerCurve";
import type { PowerCurvePoint } from "./types";

const point = (duration_s: number, power_w: number): PowerCurvePoint => ({ duration_s, power_w, activity_id: "x", start_time: "2026-06-01T00:00:00Z" });

describe("compareCurves", () => {
  it("lines two ranges up on the union of their durations", () => {
    const rows = compareCurves([point(5, 900), point(60, 500)], [point(5, 850), point(300, 350)]);
    expect(rows).toEqual([
      { duration_s: 5, a: 900, b: 850 },
      { duration_s: 60, a: 500, b: null },
      { duration_s: 300, a: null, b: 350 },
    ]);
  });

  it("converts to W/kg with each range's own weight", () => {
    const [row] = compareCurves([point(5, 900)], [point(5, 800)], { a: 75, b: 80 });
    expect(row.a).toBeCloseTo(12);
    expect(row.b).toBeCloseTo(10);
  });
});

describe("headlinePowers", () => {
  it("picks the efforts riders quote and leaves gaps as null", () => {
    const result = headlinePowers([point(5, 900), point(300, 350)]);
    expect(result.map((r) => [r.duration_s, r.point?.power_w ?? null])).toEqual([[5, 900], [60, null], [300, 350], [1200, null]]);
  });
});

describe("changePercent", () => {
  it("compares two values and refuses to divide by nothing", () => {
    expect(changePercent(200, 220)).toBeCloseTo(10);
    expect(changePercent(200, 180)).toBeCloseTo(-10);
    expect(changePercent(null, 5)).toBeNull();
    expect(changePercent(0, 5)).toBeNull();
  });
});

describe("rangeBounds", () => {
  const now = new Date("2026-06-30T12:00:00Z");

  it("bounds a rolling window ending now", () => {
    const { start, end } = rangeBounds("28d", now);
    expect(start).toBe("2026-06-02T12:00:00.000Z");
    expect(end).toBeUndefined();
  });

  it("can end earlier, for the period before", () => {
    expect(rangeBounds("28d", now, 28)).toEqual({ start: "2026-05-05T12:00:00.000Z", end: "2026-06-02T12:00:00.000Z" });
  });

  it("'all' has no start", () => {
    expect(rangeBounds("all", now)).toEqual({});
    expect(rangeBounds("all", now, 28)).toEqual({ end: "2026-06-02T12:00:00.000Z" });
  });
});
