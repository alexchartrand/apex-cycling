import type { SessionSummary } from "../training/types";
import { localDay } from "./format";
import type { Activity } from "./types";

/**
 * One row of the log: a sqorz session (with the recordings of it riding along)
 * or an activity that belongs to no session.
 */
export type LogItem =
  | { kind: "session"; day: string; at: string; session: SessionSummary; activities: Activity[] }
  | { kind: "activity"; day: string; at: string; activity: Activity };

/** Sessions and activities as one newest-first list. Recordings linked to a session fold into it. */
export function mergeLog(sessions: SessionSummary[], activities: Activity[]): LogItem[] {
  const linked = new Map<string, Activity[]>();
  const loose: Activity[] = [];
  for (const activity of activities) {
    if (activity.external_event_id && sessions.some((s) => s.external_event_id === activity.external_event_id)) {
      linked.set(activity.external_event_id, [...(linked.get(activity.external_event_id) ?? []), activity]);
    } else {
      loose.push(activity);
    }
  }
  const items: LogItem[] = [
    ...sessions.map((session): LogItem => ({
      kind: "session",
      day: session.event_date,
      at: session.first_lap_at ?? `${session.event_date}T00:00:00`,
      session,
      activities: linked.get(session.external_event_id) ?? [],
    })),
    ...loose.map((activity): LogItem => ({ kind: "activity", day: localDay(activity.start_time), at: activity.start_time, activity })),
  ];
  return items.sort((a, b) => (a.day === b.day ? new Date(b.at).getTime() - new Date(a.at).getTime() : a.day < b.day ? 1 : -1));
}

export function groupItemsByMonth(items: LogItem[]): { month: string; items: LogItem[] }[] {
  const groups: { month: string; items: LogItem[] }[] = [];
  for (const item of items) {
    const month = item.day.slice(0, 7);
    const last = groups[groups.length - 1];
    if (last?.month === month) last.items.push(item);
    else groups.push({ month, items: [item] });
  }
  return groups;
}

export interface CalendarDay {
  day: string;
  inMonth: boolean;
  items: LogItem[];
}

function ymd(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

/** Monday-first weeks covering a month, each day holding that day's log items. */
export function monthCalendar(year: number, monthIndex: number, items: LogItem[]): CalendarDay[][] {
  const byDay = new Map<string, LogItem[]>();
  for (const item of items) byDay.set(item.day, [...(byDay.get(item.day) ?? []), item]);

  const first = new Date(year, monthIndex, 1);
  const cursor = new Date(first);
  cursor.setDate(1 - ((first.getDay() + 6) % 7));
  const weeks: CalendarDay[][] = [];
  do {
    const week: CalendarDay[] = [];
    for (let i = 0; i < 7; i++) {
      const day = ymd(cursor);
      week.push({ day, inMonth: cursor.getMonth() === monthIndex, items: byDay.get(day) ?? [] });
      cursor.setDate(cursor.getDate() + 1);
    }
    weeks.push(week);
  } while (cursor.getMonth() === monthIndex);
  return weeks;
}

const DAY_PARAM = /^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$/;

function dateOf(day: string): Date {
  const [y, m, d] = day.split("-").map(Number);
  return new Date(y, m - 1, d);
}

/** The Monday (`YYYY-MM-DD`) of the week holding local day `day`. */
export function weekStart(day: string): string {
  const date = dateOf(day);
  date.setDate(date.getDate() - ((date.getDay() + 6) % 7));
  return ymd(date);
}

/** `day` moved by whole days (local calendar, so DST never shifts it). */
export function shiftDay(day: string, days: number): string {
  const date = dateOf(day);
  date.setDate(date.getDate() + days);
  return ymd(date);
}

/** `?week=` (any day of it) → its Monday; null when absent or not a date. */
export function parseWeekParam(param: string | null): string | null {
  return param && DAY_PARAM.test(param) ? weekStart(param) : null;
}

/** One Monday-first week, each day holding that day's log items (every day counts as "in" the period). */
export function weekCalendar(monday: string, items: LogItem[]): CalendarDay[][] {
  const byDay = new Map<string, LogItem[]>();
  for (const item of items) byDay.set(item.day, [...(byDay.get(item.day) ?? []), item]);
  const week = Array.from({ length: 7 }, (_, i) => {
    const day = shiftDay(monday, i);
    return { day, inMonth: true, items: byDay.get(day) ?? [] };
  });
  return [week];
}

/** Plans still to ride this week: `planned`, from `today` to Sunday, soonest first. */
export function upcomingThisWeek<P extends { planned_date: string; status: string }>(plans: P[], today: string): P[] {
  const sunday = shiftDay(weekStart(today), 6);
  return plans
    .filter((plan) => plan.status === "planned" && plan.planned_date >= today && plan.planned_date <= sunday)
    .sort((a, b) => (a.planned_date < b.planned_date ? -1 : a.planned_date > b.planned_date ? 1 : 0));
}
