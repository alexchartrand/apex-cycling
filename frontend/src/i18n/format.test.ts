import { describe, expect, it } from "vitest";
import { createFormatters, localIsoDate, parseLocalDate } from "./format";

const en = createFormatters("en");
const fr = createFormatters("fr");

describe("lapTime", () => {
  it("uses a decimal point in English and a comma in French", () => {
    expect(en.lapTime(71_441)).toBe("1:11.441");
    expect(fr.lapTime(71_441)).toBe("1:11,441");
  });

  it("handles sub-minute, rounding edge and missing values", () => {
    expect(en.lapTime(11_482)).toBe("0:11.482");
    expect(en.lapTime(59_999.6)).toBe("1:00.000");
    expect(fr.lapTime(null)).toBe("—");
  });
});

describe("seconds and deltas", () => {
  it("formats bare seconds", () => {
    expect(en.seconds(11_482)).toBe("11.482");
    expect(fr.seconds(11_482, 2)).toBe("11,48");
  });

  it("signs deltas with a true minus", () => {
    expect(en.deltaSeconds(-214)).toBe("−0.214");
    expect(fr.deltaSeconds(380)).toBe("+0,380");
    expect(en.deltaSeconds(0)).toBe("±0.000");
  });
});

describe("speed and distance", () => {
  it("derives km/h from a 250 m lap", () => {
    expect(en.speedKmh(250, 17_900)).toBe("50.3");
    expect(fr.speedKmh(250, 17_900)).toBe("50,3");
    expect(en.speedKmh(250, 0)).toBe("—");
  });

  it("switches m → km at 1000 m", () => {
    expect(en.distance(250)).toBe("250 m");
    expect(en.distance(35_500)).toBe("35.5 km");
    expect(fr.distance(35_500)).toBe("35,5 km");
  });
});

describe("duration", () => {
  it("formats h:mm over an hour, m:ss under", () => {
    expect(en.duration(9600)).toBe("2:40");
    expect(en.duration(272)).toBe("4:32");
  });
});

describe("dates", () => {
  it("parses date-only ISO strings as local dates, not UTC", () => {
    const d = parseLocalDate("2026-10-17");
    expect([d.getFullYear(), d.getMonth(), d.getDate()]).toEqual([2026, 9, 17]);
  });

  it("formats in the UI language", () => {
    expect(en.date("2026-10-17", "dayMonth")).toMatch(/Oct\.? 17/);
    expect(fr.date("2026-10-17", "dayMonth")).toMatch(/17 oct\.?/);
  });

  it("formats relative times", () => {
    const now = new Date("2026-10-19T20:00:00Z");
    expect(en.relative(new Date("2026-10-19T19:48:00Z"), now)).toBe("12 minutes ago");
    expect(fr.relative(new Date("2026-10-19T19:48:00Z"), now)).toBe("il y a 12 minutes");
    expect(en.relative(new Date("2026-10-18T20:00:00Z"), now)).toBe("yesterday");
    expect(fr.relative(new Date("2026-10-18T20:00:00Z"), now)).toBe("hier");
  });
});

describe("localIsoDate", () => {
  it("uses the local calendar day, not the UTC one", () => {
    // 23:30 local on Oct 17 is already Oct 18 in UTC anywhere west of Greenwich.
    expect(localIsoDate(new Date(2026, 9, 17, 23, 30))).toBe("2026-10-17");
    expect(localIsoDate(new Date(2026, 0, 5))).toBe("2026-01-05");
  });

  it("round-trips with parseLocalDate", () => {
    expect(localIsoDate(parseLocalDate("2026-03-09"))).toBe("2026-03-09");
  });
});
