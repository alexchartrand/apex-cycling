import { describe, expect, it } from "vitest";
import { browserTimeZone, isValidTimeZone } from "./timeZone";

describe("isValidTimeZone", () => {
  it("accepts IANA zones", () => {
    expect(isValidTimeZone("America/Toronto")).toBe(true);
    expect(isValidTimeZone("UTC")).toBe(true);
  });

  it("rejects blanks and nonsense", () => {
    expect(isValidTimeZone("")).toBe(false);
    expect(isValidTimeZone("  ")).toBe(false);
    expect(isValidTimeZone("Mars/Olympus_Mons")).toBe(false);
  });
});

describe("browserTimeZone", () => {
  it("is a zone the browser accepts", () => {
    expect(isValidTimeZone(browserTimeZone())).toBe(true);
  });
});
