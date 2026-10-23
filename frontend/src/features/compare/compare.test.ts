import { describe, expect, it } from "vitest";
import type { Effort } from "../training/types";
import { compareHref, cumulativeDelta, defaultEffort, better, lapRows, pickEffort, splitRows } from "./compare";

function effort(lapTimes: (number | null)[], splits: (number | null)[] = [], first = "lap-1"): Effort {
  return {
    index: 1,
    track_id: "t",
    track_name: "Track",
    label: null,
    start_time: "2026-07-07T13:00:00Z",
    start_type: "flying",
    lap_ids: lapTimes.map((_, i) => (i === 0 ? first : `${first}-${i}`)),
    completed_lap_count: lapTimes.filter((t) => t != null).length,
    lap_times_ms: lapTimes,
    total_time_ms: null,
    best_lap_ms: null,
    distance_m: null,
    avg_speed_kmh: null,
    half_lap_splits: splits.map((time_ms, index) => ({ index, from_line: index % 2 ? "P2" : "P1", to_line: index % 2 ? "P1" : "P2", time_ms })),
  };
}

describe("lapRows", () => {
  it("lines laps up by number and lets the shorter effort end early", () => {
    expect(lapRows(effort([20000, 21000]), effort([19000]))).toEqual([
      { lap: 1, a: 20000, b: 19000 },
      { lap: 2, a: 21000, b: null },
    ]);
  });
});

describe("cumulativeDelta", () => {
  it("accumulates B minus A", () => {
    expect(cumulativeDelta(effort([20000, 20000, 20000]), effort([19500, 20500, 20000]))).toEqual([
      { lap: 1, deltaMs: -500, lapDeltaMs: -500 },
      { lap: 2, deltaMs: 0, lapDeltaMs: 500 },
      { lap: 3, deltaMs: 0, lapDeltaMs: 0 },
    ]);
  });

  it("stops at the first lap one side didn't finish", () => {
    expect(cumulativeDelta(effort([20000, null, 20000]), effort([19000, 19000, 19000]))).toEqual([{ lap: 1, deltaMs: -1000, lapDeltaMs: -1000 }]);
    expect(cumulativeDelta(effort([20000, 20000]), effort([19000]))).toHaveLength(1);
  });
});

describe("splitRows", () => {
  it("pairs splits by position and drops pairs with no time", () => {
    const rows = splitRows(effort([], [10000, 10500, null]), effort([], [9800, 10400, null, 9900]));
    expect(rows).toEqual([
      { n: 1, label: "P1→P2", a: 10000, b: 9800 },
      { n: 2, label: "P2→P1", a: 10500, b: 10400 },
      { n: 4, label: "P2→P1", a: null, b: 9900 },
    ]);
  });
});

describe("choosing efforts", () => {
  const short = effort([20000, 20000], [], "short");
  const long = effort([20000, 20000, 20000, 20000], [], "long");
  const tie = effort([20000, 20000, 20000, 20000], [], "tie");

  it("defaults to the longest, earliest on a tie", () => {
    expect(defaultEffort([short, long, tie])).toBe(long);
    expect(defaultEffort([])).toBeUndefined();
  });

  it("honours the first-lap id, else the default", () => {
    expect(pickEffort([short, long], "short")).toBe(short);
    expect(pickEffort([short, long], "gone")).toBe(long);
    expect(pickEffort([short, long], null)).toBe(long);
  });
});

describe("better", () => {
  it("is the lower figure unless told otherwise", () => {
    expect(better(10, 11)).toBe("a");
    expect(better(11, 10)).toBe("b");
    expect(better(10, 10)).toBeNull();
    expect(better(null, 10)).toBeNull();
    expect(better(60, 55, "higher")).toBe("a");
    expect(better(55, 60, "higher")).toBe("b");
  });
});

describe("compareHref", () => {
  it("writes both sides into the address", () => {
    expect(compareHref({ eventId: "e1", firstLapId: "l1" })).toBe("/compare?a=e1&ae=l1");
    expect(compareHref({ eventId: "e1" }, { eventId: "e 2", firstLapId: "l2" })).toBe("/compare?a=e1&b=e+2&be=l2");
  });
});
