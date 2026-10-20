import type { Formatters } from "../../i18n/format";

export const MAX_RESULT_MS = 7_200_000; // mirrors the backend's bound (2 h)

/**
 * Reads a time typed as "1:12.345", "72.3", "72,3" or "0:11.736" (comma or
 * dot decimals, optional minutes) into ms. Null when it isn't a plausible
 * time: empty, malformed, zero or over two hours.
 */
export function parseTimeInput(text: string): number | null {
  const match = /^\s*(?:(\d{1,3}):)?(\d{1,4})(?:[.,](\d{1,3}))?\s*$/.exec(text);
  if (!match) return null;
  const [, minutes = "0", seconds, fraction = ""] = match;
  if (minutes !== "0" && Number(seconds) >= 60) return null; // "1:75" is a typo, not 2:15
  const ms = Number(minutes) * 60_000 + Number(seconds) * 1000 + Number(fraction.padEnd(3, "0"));
  return ms > 0 && ms <= MAX_RESULT_MS ? ms : null;
}

/** ms → what you'd type back in: "11.736" under a minute (locale decimal), "1:12.345" above. */
export function timeToInput(ms: number, fmt: Pick<Formatters, "seconds" | "lapTime">): string {
  return ms < 60_000 ? fmt.seconds(ms) : fmt.lapTime(ms);
}

/** A record time as shown on the board: "11,736 s" under a minute, "1:12,345" above. */
export function formatRecordTime(ms: number, fmt: Pick<Formatters, "seconds" | "lapTime">): string {
  return ms < 60_000 ? `${fmt.seconds(ms)} s` : fmt.lapTime(ms);
}
