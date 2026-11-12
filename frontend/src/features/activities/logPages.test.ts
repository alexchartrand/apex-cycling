import { describe, expect, it } from "vitest";
import { logWindows, newestMonth, pageWindow } from "./logPages";

describe("pageWindow", () => {
  it("covers three whole months ending with the given one, across a year boundary", () => {
    expect(pageWindow("2026-05")).toEqual({ from: "2026-03-01", to: "2026-05-31" });
    expect(pageWindow("2026-01")).toEqual({ from: "2025-11-01", to: "2026-01-31" });
    expect(pageWindow("2024-02").to).toBe("2024-02-29");
  });
});

describe("newestMonth", () => {
  it("takes the newer source, or null when both are empty", () => {
    expect(newestMonth("2026-03-04", "2026-05-01")).toBe("2026-05");
    expect(newestMonth(null, "2025-12-31")).toBe("2025-12");
    expect(newestMonth(null, undefined)).toBeNull();
  });
});

describe("logWindows", () => {
  it("starts with the newest page, open-ended", () => {
    expect(logWindows("2026-05", [])).toEqual([{ from: "2026-03-01" }]);
  });

  it("stretches the first page down to the older ones when the newest month moved on", () => {
    // Loaded while May was the newest month, then a session arrived in July.
    const older = [pageWindow("2026-02")];
    expect(logWindows("2026-07", older)).toEqual([{ from: "2026-03-01" }, { from: "2025-12-01", to: "2026-02-28" }]);
  });
});
