import { localIsoDate, parseLocalDate } from "../../i18n/format";

/** `YYYY-MM-DD` moved by `days` (local calendar, so no DST slip). */
export function addDays(day: string, days: number): string {
  const date = parseLocalDate(day);
  date.setDate(date.getDate() + days);
  return localIsoDate(date);
}

/**
 * The instants bounding local days `from`…`to` (inclusive) — `start` at the
 * first's midnight, `end` (exclusive) at the midnight after the last — for
 * the activities endpoint, whose bounds are timestamps.
 */
export function dayBounds(from: string, to: string): { start: string; end: string } {
  return { start: parseLocalDate(from).toISOString(), end: parseLocalDate(addDays(to, 1)).toISOString() };
}
