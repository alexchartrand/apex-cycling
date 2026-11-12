import { addDays } from "./dayRange";

/** How many calendar months one "load more" of the Log's list adds. */
export const LOG_PAGE_MONTHS = 3;

/** Local days (`YYYY-MM-DD`), both included; no `to` = up to now and beyond. */
export interface DayWindow {
  from: string;
  to?: string;
}

function shiftMonth(month: string, delta: number): string {
  const [year, index] = month.split("-").map(Number);
  const date = new Date(year, index - 1 + delta, 1);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

/** The whole months `top` (`YYYY-MM`) and the `LOG_PAGE_MONTHS - 1` before it. */
export function pageWindow(top: string): Required<DayWindow> {
  return { from: `${shiftMonth(top, -(LOG_PAGE_MONTHS - 1))}-01`, to: addDays(`${shiftMonth(top, 1)}-01`, -1) };
}

/** The month of the newer of two days (either may be missing). */
export function newestMonth(...days: (string | null | undefined)[]): string | null {
  const newest = days.filter((d): d is string => d != null).sort().at(-1);
  return newest ? newest.slice(0, 7) : null;
}

/**
 * Every window the list shows, newest first. The first is open-ended so a
 * session in a new month lands in it, and once older pages are loaded it
 * reaches down to the newest of them, so no days fall between pages.
 */
export function logWindows(newest: string, older: Required<DayWindow>[]): DayWindow[] {
  const first: DayWindow = { from: older.length > 0 ? addDays(older[0].to, 1) : pageWindow(newest).from };
  return [first, ...older];
}
