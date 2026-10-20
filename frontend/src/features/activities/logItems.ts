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
