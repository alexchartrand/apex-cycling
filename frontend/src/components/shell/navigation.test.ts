import { describe, expect, it } from "vitest";
import {
  activeHub,
  activeNavItem,
  HUBS,
  hubTarget,
  MOBILE_TABS,
  MORE_SHEET_ITEMS,
  NAV_ITEMS,
  shownItems,
  SIDEBAR_FOOTER,
  SIDEBAR_GROUPS,
} from "./navigation";
import { SPORTS, type Sport } from "../../features/sports/registry";

const ALL = new Set<Sport>(SPORTS);

describe("activeNavItem", () => {
  it.each([
    ["/", "home"],
    ["/log", "log"],
    ["/sessions/abc123", "log"],
    ["/activities/42", "log"],
    ["/compare", "log"],
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

describe("activeHub", () => {
  it.each([
    ["/", "home"],
    ["/sessions/abc", "log"],
    ["/plans/12/edit", "train"],
    ["/workouts/new", "train"],
    ["/season", "train"],
    ["/ai-coach", "train"],
    ["/progress", "progress"],
    ["/records", "progress"],
    ["/power", "progress"],
    ["/aero", "progress"],
    ["/equipment", "gear"],
    ["/tools/gearing", "gear"],
    ["/join", "club"],
  ])("%s → %s", (path, key) => {
    expect(activeHub(path)?.key).toBe(key);
  });

  it("is undefined outside the navigation", () => {
    expect(activeHub("/admin")).toBeUndefined();
  });
});

describe("hub pages", () => {
  it("hides the AI coach until it is enabled", () => {
    expect(shownItems(HUBS.train, { aiCoach: false, sports: ALL }).map((i) => i.key)).toEqual(["plans", "workouts", "season"]);
    expect(shownItems(HUBS.train, { aiCoach: true, sports: ALL }).map((i) => i.key)).toContain("aiCoach");
  });

  it("links a hub to its first page", () => {
    expect(hubTarget(HUBS.progress, { aiCoach: false, sports: ALL })).toBe("/progress");
    expect(hubTarget(HUBS.gear, { aiCoach: false, sports: ALL })).toBe("/equipment");
  });

  it("hides the pages of sports the athlete doesn't do", () => {
    const strength = { aiCoach: false, sports: new Set<Sport>(["strength"]) };
    expect(shownItems(HUBS.progress, strength).map((i) => i.key)).toEqual(["progress"]);
    expect(shownItems(HUBS.gear, strength)).toEqual([]);
    const road = { aiCoach: false, sports: new Set<Sport>(["cycling"]) };
    expect(shownItems(HUBS.progress, road).map((i) => i.key)).toEqual(["progress", "power", "aero"]);
    expect(shownItems(HUBS.gear, road).map((i) => i.key)).toEqual(["equipment"]);
  });

  it("puts every page in exactly one hub", () => {
    const keys = Object.values(HUBS).flatMap((hub) => hub.items.map((item) => item.key));
    expect(new Set(keys).size).toBe(keys.length);
    expect(new Set(keys)).toEqual(new Set(Object.keys(NAV_ITEMS)));
  });
});

describe("navigation coverage", () => {
  it("every page is reachable on desktop and on phones", () => {
    const desktop = new Set(
      [...SIDEBAR_GROUPS.flatMap((g) => g.hubs), ...SIDEBAR_FOOTER].flatMap((hub) => hub.items.map((i) => i.key)),
    );
    // On phones a tab opens its hub, whose sub-tabs reach the rest of it.
    const phone = new Set([...MOBILE_TABS.flatMap((hub) => hub.items), ...MORE_SHEET_ITEMS].map((i) => i.key));
    for (const key of Object.keys(NAV_ITEMS)) {
      expect(desktop.has(key as never), `${key} missing from sidebar`).toBe(true);
      expect(phone.has(key as never), `${key} missing on phones`).toBe(true);
    }
  });
});
