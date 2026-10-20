import { describe, expect, it } from "vitest";
import { createFormatters } from "../../i18n/format";
import { formatRecordTime, MAX_RESULT_MS, parseTimeInput, timeToInput } from "./timeInput";

describe("parseTimeInput", () => {
  it.each([
    ["11.736", 11_736],
    ["11,736", 11_736],
    ["72.3", 72_300],
    ["72", 72_000],
    ["1:12.345", 72_345],
    ["0:11.736", 11_736],
    ["1:12", 72_000],
    ["  1:12,5 ", 72_500],
    ["6:12.001", 372_001],
    ["120:00", MAX_RESULT_MS],
  ])("reads %j as %i ms", (text, ms) => {
    expect(parseTimeInput(text)).toBe(ms);
  });

  it.each(["", "  ", "abc", "1:2:3", "1:75", "1:60.0", "-5", "0", "0.000", "11.7361", "121:00", "1.", ".5", "1:12.", "99999"])(
    "rejects %j",
    (text) => {
      expect(parseTimeInput(text)).toBeNull();
    },
  );

  it("pads a short fraction as decimals, not milliseconds", () => {
    expect(parseTimeInput("11.7")).toBe(11_700);
    expect(parseTimeInput("11.07")).toBe(11_070);
  });
});

describe("time formatting", () => {
  const en = createFormatters("en");
  const fr = createFormatters("fr");

  it("shows short times as seconds and long ones as m:ss", () => {
    expect(formatRecordTime(11_736, en)).toBe("11.736 s");
    expect(formatRecordTime(11_736, fr)).toBe("11,736 s");
    expect(formatRecordTime(72_345, en)).toBe("1:12.345");
    expect(formatRecordTime(72_345, fr)).toBe("1:12,345");
  });

  it("round-trips through the input parser in either language", () => {
    for (const fmt of [en, fr]) {
      for (const ms of [11_736, 59_999, 60_000, 72_345, 372_001]) {
        expect(parseTimeInput(timeToInput(ms, fmt))).toBe(ms);
      }
    }
  });
});
