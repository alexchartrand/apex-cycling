import { Activity as ActivityIcon, Bike, Dumbbell, Gauge, House, type LucideIcon } from "lucide-react";
import type { LogItem } from "./logItems";
import type { Activity, ActivityType, ActivityUpdate } from "./types";

/** Every kind of training, in the order pickers and legends show them. */
export const ACTIVITY_TYPES: readonly ActivityType[] = ["track_cycling", "cycling", "indoor_cycling", "strength", "other"];

/** The type's color, a theme token (`--color-type-*` in tokens.css). */
export function typeColor(type: ActivityType): string {
  return `var(--color-type-${type})`;
}

const ICONS: Record<ActivityType, LucideIcon> = {
  cycling: Bike,
  track_cycling: Gauge,
  indoor_cycling: House,
  strength: Dumbbell,
  other: ActivityIcon,
};

export function typeIcon(type: ActivityType): LucideIcon {
  return ICONS[type] ?? ActivityIcon; // a type newer than this build
}

/** A sqorz session is track cycling; an activity is what it says. */
export function typeOfLogItem(item: LogItem): ActivityType {
  return item.kind === "session" ? "track_cycling" : item.activity.activity_type;
}

export function isActivityType(value: string): value is ActivityType {
  return (ACTIVITY_TYPES as readonly string[]).includes(value);
}

/** `?types=cycling,strength` → the types shown; null (absent or nothing valid) = all of them. */
export function parseTypeFilter(param: string | null): Set<ActivityType> | null {
  if (!param) return null;
  const types = param.split(",").filter(isActivityType);
  return types.length ? new Set(types) : null;
}

/** The query value for a set of selected types; null when none is selected (no filter). */
export function typeFilterParam(types: Set<ActivityType> | null): string | null {
  if (!types || types.size === 0) return null;
  return ACTIVITY_TYPES.filter((type) => types.has(type)).join(",");
}

/** Toggles one type in the filter: from no filter it shows only that type; deselecting the last one clears the filter (null = everything). */
export function toggleType(selected: Set<ActivityType> | null, type: ActivityType): Set<ActivityType> | null {
  const next = new Set(selected ?? []);
  if (next.has(type)) next.delete(type);
  else next.add(type);
  return next.size === 0 ? null : next;
}

/** The type picker's "follow the source" choice. */
export const AUTO_TYPE = "auto";

/** What the name/type dialog changes on the activity (empty when its fields match it). */
export function identityChanges(activity: Activity, name: string, type: string): ActivityUpdate {
  const changes: ActivityUpdate = {};
  if (name.trim() !== (activity.name ?? "")) changes.name = name.trim() || null;
  const current = activity.activity_type_manual ? activity.activity_type : AUTO_TYPE;
  if (type !== current) changes.activity_type = isActivityType(type) ? type : null;
  return changes;
}

export function filterLogItems(items: LogItem[], shown: Set<ActivityType> | null): LogItem[] {
  return shown ? items.filter((item) => shown.has(typeOfLogItem(item))) : items;
}
