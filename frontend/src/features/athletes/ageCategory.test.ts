import { describe, expect, it } from "vitest";
import i18n from "../../i18n";
import { ageCategoryLabel } from "./ageCategory";

describe("ageCategoryLabel", () => {
  const t = i18n.getFixedT("en", "common");

  it("labels youth and elite codes", () => {
    expect(ageCategoryLabel("U17", t)).toBe("U17");
    expect(ageCategoryLabel("U19", t)).toBe("Junior (U19)");
    expect(ageCategoryLabel("ELITE", t)).toBe("Elite");
  });

  it("expands masters codes into their five-year band", () => {
    expect(ageCategoryLabel("M35", t)).toBe("Master 35–39");
    expect(ageCategoryLabel("M30", t)).toBe("Master 30–34");
  });

  it("falls back to the raw code for one it doesn't know", () => {
    expect(ageCategoryLabel("U9", t)).toBe("U9");
  });
});
