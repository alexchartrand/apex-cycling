/** 5 → "5 s", 90 → "1:30", 1200 → "20 min", 5400 → "1 h 30". */
export function durationLabel(seconds: number): string {
  if (seconds < 60) return `${seconds} s`;
  if (seconds < 3600) return seconds % 60 === 0 ? `${seconds / 60} min` : `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
  const hours = seconds / 3600;
  return Number.isInteger(hours) ? `${hours} h` : `${Math.floor(seconds / 3600)} h ${Math.round((seconds % 3600) / 60)}`;
}

export function mpsToKmh(mps: number | null | undefined): number | null {
  return mps == null ? null : mps * 3.6;
}

/** Local calendar day (YYYY-MM-DD) of an instant, in the browser's zone. */
export function localDay(iso: string): string {
  const date = new Date(iso);
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

/** Ticks for a log-scaled duration axis: the standard efforts riders compare. */
export const CURVE_TICKS_S = [1, 5, 15, 30, 60, 300, 1200, 3600, 10800] as const;
