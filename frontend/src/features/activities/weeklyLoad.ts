import { ACTIVITY_TYPES } from "./activityTypes";
import type { ActivityType, WeeklyLoad } from "./types";

export type WeeklyMetric = "hours" | "tss";

export type WeeklyRow = { week: string } & Partial<Record<ActivityType, number>>;

/** One chart row per week (hours or load per type) and the types that appear at all, in legend order. */
export function weeklyChartRows(weeks: WeeklyLoad[], metric: WeeklyMetric): { rows: WeeklyRow[]; types: ActivityType[] } {
  const seen = new Set<ActivityType>();
  const rows = weeks.map((week) => {
    const row: WeeklyRow = { week: week.week_start };
    for (const entry of week.types) {
      const value = metric === "hours" ? entry.seconds / 3600 : entry.tss;
      if (value <= 0) continue;
      row[entry.activity_type] = Math.round(value * 10) / 10;
      seen.add(entry.activity_type);
    }
    return row;
  });
  return { rows, types: ACTIVITY_TYPES.filter((type) => seen.has(type)) };
}
