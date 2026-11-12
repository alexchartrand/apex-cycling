import { describe, expect, it } from "vitest";
import { weekdayName, warningKey } from "./proposalText";
import { headline } from "./reportText";

describe("headline", () => {
  it("takes the first non-empty line without Markdown", () => {
    expect(headline("\n## **Solid** week\nMore text")).toBe("Solid week");
    expect(headline("")).toBe("");
  });
});

describe("proposal text", () => {
  it("maps warnings to their keys", () => {
    expect(warningKey("over_hours:2026-11-16")).toBe("over_hours");
    expect(warningKey("not_available_day")).toBe("not_available_day");
    expect(warningKey("something")).toBe("other");
  });

  it("names ISO weekdays, Monday first", () => {
    expect(weekdayName(1, "en", "long")).toBe("Monday");
    expect(weekdayName(7, "fr", "long")).toBe("dimanche");
  });
});
