/** "over_hours:2026-11-16" → "over_hours"; the translation keys of the proposal warnings. */
export function warningKey(warning: string): "not_available_day" | "over_hours" | "other" {
  const key = warning.split(":")[0];
  return key === "not_available_day" || key === "over_hours" ? key : "other";
}

/** ISO weekdays, Monday first. */
export const WEEKDAYS = [1, 2, 3, 4, 5, 6, 7] as const;

/** A reference Monday, so `Intl` can name the weekdays in the viewer's language. */
export function weekdayName(isoDay: number, locale: string, style: "long" | "short" = "short"): string {
  const day = new Date(Date.UTC(2024, 0, isoDay)); // 2024-01-01 is a Monday
  return new Intl.DateTimeFormat(locale, { weekday: style, timeZone: "UTC" }).format(day);
}
