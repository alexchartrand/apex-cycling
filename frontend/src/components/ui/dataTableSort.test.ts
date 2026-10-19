import { describe, expect, it } from "vitest";
import { nextSort, sortRows } from "./dataTableSort";

const laps = [
  { id: "a", ms: 18_200 },
  { id: "b", ms: null },
  { id: "c", ms: 17_900 },
  { id: "d", ms: 18_200 },
];

describe("sortRows", () => {
  it("sorts ascending with missing values last", () => {
    expect(sortRows(laps, (l) => l.ms, "asc").map((l) => l.id)).toEqual(["c", "a", "d", "b"]);
  });

  it("keeps missing values last when descending too", () => {
    expect(sortRows(laps, (l) => l.ms, "desc").map((l) => l.id)).toEqual(["a", "d", "c", "b"]);
  });

  it("is stable for ties", () => {
    const sorted = sortRows(laps, (l) => l.ms, "asc");
    expect(sorted.indexOf(laps[0])).toBeLessThan(sorted.indexOf(laps[3]));
  });

  it("compares strings naturally", () => {
    const rows = ["Lap 10", "Lap 2", "Lap 1"];
    expect(sortRows(rows, (r) => r, "asc")).toEqual(["Lap 1", "Lap 2", "Lap 10"]);
  });

  it("does not mutate the input", () => {
    const copy = [...laps];
    sortRows(laps, (l) => l.ms, "asc");
    expect(laps).toEqual(copy);
  });
});

describe("nextSort", () => {
  it("cycles asc → desc → off on the same column", () => {
    const asc = nextSort(null, "time");
    expect(asc).toEqual({ columnId: "time", direction: "asc" });
    const desc = nextSort(asc, "time");
    expect(desc).toEqual({ columnId: "time", direction: "desc" });
    expect(nextSort(desc, "time")).toBeNull();
  });

  it("starts ascending when switching columns", () => {
    expect(nextSort({ columnId: "time", direction: "desc" }, "lap")).toEqual({ columnId: "lap", direction: "asc" });
  });
});
