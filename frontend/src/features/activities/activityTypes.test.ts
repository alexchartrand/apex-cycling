import { describe, expect, it } from "vitest";
import {
  ACTIVITY_TYPES,
  filterLogItems,
  identityChanges,
  parseTypeFilter,
  toggleType,
  typeFilterParam,
  typeOfLogItem,
} from "./activityTypes";
import type { LogItem } from "./logItems";
import type { Activity } from "./types";
import { weeklyChartRows } from "./weeklyLoad";

const activity = (over: Partial<Activity> = {}) =>
  ({ id: "a", name: "Ride", activity_type: "cycling", activity_type_manual: false, ...over }) as Activity;
const activityItem = (over: Partial<Activity> = {}): LogItem => ({ kind: "activity", day: "2026-06-01", at: "", activity: activity(over) });
const sessionItem = { kind: "session", day: "2026-06-01", at: "", session: {}, activities: [] } as unknown as LogItem;

describe("activity types", () => {
  it("gives sessions track cycling and activities their own type", () => {
    expect(typeOfLogItem(sessionItem)).toBe("track_cycling");
    expect(typeOfLogItem(activityItem({ activity_type: "strength" }))).toBe("strength");
  });

  it("parses and writes the type filter", () => {
    expect(parseTypeFilter(null)).toBeNull();
    expect(parseTypeFilter("bogus")).toBeNull();
    expect([...parseTypeFilter("strength,bogus,cycling")!]).toEqual(["strength", "cycling"]);
    expect(typeFilterParam(new Set(["strength", "cycling"]))).toBe("cycling,strength");
    expect(typeFilterParam(new Set(ACTIVITY_TYPES))).toBe(ACTIVITY_TYPES.join(","));
    expect(typeFilterParam(null)).toBeNull();
  });

  it("toggles types: the first pick shows only it, clearing the last shows everything", () => {
    expect([...toggleType(null, "other")!]).toEqual(["other"]);
    expect(toggleType(new Set(["cycling"]), "cycling")).toBeNull();
    expect([...toggleType(new Set(["cycling"]), "strength")!]).toEqual(["cycling", "strength"]);
    expect([...toggleType(new Set(["cycling", "strength"]), "cycling")!]).toEqual(["strength"]);
  });

  it("filters log items", () => {
    const items = [sessionItem, activityItem(), activityItem({ activity_type: "strength" })];
    expect(filterLogItems(items, null)).toHaveLength(3);
    expect(filterLogItems(items, new Set(["strength"]))).toEqual([items[2]]);
  });

  it("sends only what the name/type dialog changed", () => {
    const ride = activity();
    expect(identityChanges(ride, "Ride", "auto")).toEqual({});
    expect(identityChanges(ride, "  ", "auto")).toEqual({ name: null });
    expect(identityChanges(ride, "Ride", "indoor_cycling")).toEqual({ activity_type: "indoor_cycling" });
    // A chosen type stays until "automatic" is picked again.
    const chosen = activity({ activity_type: "indoor_cycling", activity_type_manual: true });
    expect(identityChanges(chosen, "Ride", "indoor_cycling")).toEqual({});
    expect(identityChanges(chosen, "Ride", "auto")).toEqual({ activity_type: null });
  });
});

describe("weeklyChartRows", () => {
  const weeks = [
    { week_start: "2026-06-01", types: [{ activity_type: "strength" as const, seconds: 1800, tss: 0 }, { activity_type: "cycling" as const, seconds: 5400, tss: 70 }] },
    { week_start: "2026-06-08", types: [] },
  ];

  it("puts one row per week and lists the types in legend order", () => {
    expect(weeklyChartRows(weeks, "hours")).toEqual({
      rows: [{ week: "2026-06-01", strength: 0.5, cycling: 1.5 }, { week: "2026-06-08" }],
      types: ["cycling", "strength"],
    });
  });

  it("leaves out types with no load when showing load", () => {
    expect(weeklyChartRows(weeks, "tss").types).toEqual(["cycling"]);
  });
});
