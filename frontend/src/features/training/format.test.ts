import { describe, expect, it } from "vitest";
import { formatKm, formatMs } from "./format";

describe("formatMs", () => {
  it("renders a dash for missing values", () => {
    expect(formatMs(null)).toBe("—");
    expect(formatMs(undefined)).toBe("—");
  });

  it("formats sub-minute and multi-minute times as m:ss.mmm", () => {
    expect(formatMs(11_234)).toBe("0:11.234");
    expect(formatMs(65_432)).toBe("1:05.432");
    expect(formatMs(272_100)).toBe("4:32.100");
  });

  it("never rounds seconds up to 60", () => {
    expect(formatMs(59_999.6)).toBe("1:00.000");
  });
});

describe("formatKm", () => {
  it("formats with two decimals", () => {
    expect(formatKm(4)).toBe("4.00 km");
  });
});
