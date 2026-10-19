import { intlLocale, type Language } from "./language";

const DASH = "—";

/**
 * "2026-10-17" → a Date at LOCAL midnight. `new Date("2026-10-17")` parses
 * date-only ISO strings as UTC, which renders as the previous day anywhere
 * west of Greenwich (i.e. in Québec).
 */
export function parseLocalDate(value: string | Date): Date {
  if (value instanceof Date) return value;
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (match) return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return new Date(value);
}

/** A Date → "YYYY-MM-DD" for its LOCAL calendar day (toISOString() would give the UTC day). */
export function localIsoDate(value: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
}

export type DateStyle = "short" | "medium" | "long" | "weekday" | "dayMonth";

const DATE_OPTIONS: Record<DateStyle, Intl.DateTimeFormatOptions> = {
  short: { year: "numeric", month: "2-digit", day: "2-digit" },
  medium: { year: "numeric", month: "short", day: "numeric" },
  long: { weekday: "long", year: "numeric", month: "long", day: "numeric" },
  weekday: { weekday: "short", month: "short", day: "numeric" },
  dayMonth: { month: "short", day: "numeric" },
};

/**
 * Formatters bound to one UI language. Lap times keep the timing-board
 * `m:ss.mmm` shape in both languages, but French uses a decimal comma
 * (`1:08,441`, `11,482 s`), as Québec timing results do.
 */
export function createFormatters(language: Language) {
  const locale = intlLocale(language);
  const decimal = language === "fr" ? "," : ".";
  const numberFormats = new Map<string, Intl.NumberFormat>();
  const numberFormat = (min: number, max: number) => {
    const key = `${min}-${max}`;
    let format = numberFormats.get(key);
    if (!format) {
      format = new Intl.NumberFormat(locale, { minimumFractionDigits: min, maximumFractionDigits: max });
      numberFormats.set(key, format);
    }
    return format;
  };
  const relativeFormat = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });

  return {
    language,
    locale,

    /** 71_441 → "1:11.441" / "1:11,441"; sub-minute keeps the "0:" prefix. */
    lapTime(ms: number | null | undefined): string {
      if (ms == null || Number.isNaN(ms)) return DASH;
      const totalMs = Math.round(ms);
      const minutes = Math.floor(totalMs / 60_000);
      const seconds = ((totalMs - minutes * 60_000) / 1000).toFixed(3).padStart(6, "0");
      return `${minutes}:${seconds.replace(".", decimal)}`;
    },

    /** 11_482 → "11.482" / "11,482" — bare seconds, for short efforts. */
    seconds(ms: number | null | undefined, digits = 3): string {
      if (ms == null || Number.isNaN(ms)) return DASH;
      return (ms / 1000).toFixed(digits).replace(".", decimal);
    },

    /** Signed difference in seconds, e.g. "−0.214" for a faster time. */
    deltaSeconds(ms: number, digits = 3): string {
      const sign = ms < 0 ? "−" : ms > 0 ? "+" : "±";
      return `${sign}${(Math.abs(ms) / 1000).toFixed(digits).replace(".", decimal)}`;
    },

    number(value: number | null | undefined, maxDigits = 1, minDigits = 0): string {
      if (value == null || Number.isNaN(value)) return DASH;
      return numberFormat(minDigits, maxDigits).format(value);
    },

    /** Speed in km/h from a distance (m) and a time (ms). */
    speedKmh(distanceM: number, ms: number | null | undefined): string {
      if (ms == null || ms <= 0) return DASH;
      return numberFormat(1, 1).format((distanceM / (ms / 1000)) * 3.6);
    },

    /** Meters → "250 m" under 1 km, "35.5 km" above. */
    distance(meters: number | null | undefined): string {
      if (meters == null || Number.isNaN(meters)) return DASH;
      if (Math.abs(meters) < 1000) return `${numberFormat(0, 0).format(meters)} m`;
      return `${numberFormat(1, 1).format(meters / 1000)} km`;
    },

    /** Seconds → "2:40 h" style "h:mm", or "m:ss" under an hour. */
    duration(totalSeconds: number | null | undefined): string {
      if (totalSeconds == null || Number.isNaN(totalSeconds)) return DASH;
      const s = Math.round(totalSeconds);
      const h = Math.floor(s / 3600);
      const m = Math.floor((s % 3600) / 60);
      if (h > 0) return `${h}:${String(m).padStart(2, "0")}`;
      return `${m}:${String(s % 60).padStart(2, "0")}`;
    },

    date(value: string | Date | null | undefined, style: DateStyle = "medium"): string {
      if (value == null) return DASH;
      return new Intl.DateTimeFormat(locale, DATE_OPTIONS[style]).format(parseLocalDate(value));
    },

    time(value: string | Date | null | undefined): string {
      if (value == null) return DASH;
      return new Intl.DateTimeFormat(locale, { hour: "numeric", minute: "2-digit" }).format(new Date(value));
    },

    /** "12 minutes ago" / "il y a 12 minutes", "yesterday" / "hier". */
    relative(value: string | Date | null | undefined, now: Date = new Date()): string {
      if (value == null) return DASH;
      const diffSeconds = (new Date(value).getTime() - now.getTime()) / 1000;
      const abs = Math.abs(diffSeconds);
      if (abs < 45) return relativeFormat.format(0, "second");
      if (abs < 3600) return relativeFormat.format(Math.round(diffSeconds / 60), "minute");
      if (abs < 86_400) return relativeFormat.format(Math.round(diffSeconds / 3600), "hour");
      if (abs < 86_400 * 30) return relativeFormat.format(Math.round(diffSeconds / 86_400), "day");
      if (abs < 86_400 * 365) return relativeFormat.format(Math.round(diffSeconds / (86_400 * 30)), "month");
      return relativeFormat.format(Math.round(diffSeconds / (86_400 * 365)), "year");
    },
  };
}

export type Formatters = ReturnType<typeof createFormatters>;
