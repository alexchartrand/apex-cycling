import { describe, expect, it } from "vitest";
import { activeNavItem, MOBILE_TABS, MORE_SHEET_ITEMS, NAV_ITEMS, SIDEBAR_FOOTER, SIDEBAR_GROUPS } from "./navigation";

describe("activeNavItem", () => {
  it.each([
    ["/", "home"],
    ["/log", "log"],
    ["/sessions/abc123", "log"],
    ["/activities/42", "log"],
    ["/records", "records"],
    ["/tools/pursuit", "tools"],
    ["/settings/security", "settings"],
  ])("%s → %s", (path, key) => {
    expect(activeNavItem(path)?.key).toBe(key);
  });

  it("does not treat prefixes of other words as matches", () => {
    expect(activeNavItem("/logout")).toBeUndefined();
    expect(activeNavItem("/toolshed")).toBeUndefined();
  });
});

describe("navigation coverage", () => {
  it("every section is reachable on desktop and on phones", () => {
    const desktop = new Set([...SIDEBAR_GROUPS.flatMap((g) => g.items), ...SIDEBAR_FOOTER].map((i) => i.key));
    const phone = new Set([...MOBILE_TABS, ...MORE_SHEET_ITEMS].map((i) => i.key));
    for (const key of Object.keys(NAV_ITEMS)) {
      expect(desktop.has(key as never), `${key} missing from sidebar`).toBe(true);
      expect(phone.has(key as never), `${key} missing on phones`).toBe(true);
    }
  });
});
