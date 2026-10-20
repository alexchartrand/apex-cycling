import type { WeekLoad } from "./types";

export type LoadDirection = "up" | "down" | "same" | "none";

export interface LoadChange {
  laps: number;
  sessions: number;
  direction: LoadDirection;
}

/**
 * This week against the one before, for a coach's glance: more laps is "up".
 * "none" when neither week had any training, so the card says nothing rather
 * than "no change".
 */
export function loadChange(thisWeek: WeekLoad, previousWeek: WeekLoad): LoadChange {
  const laps = thisWeek.laps - previousWeek.laps;
  const sessions = thisWeek.sessions - previousWeek.sessions;
  const idle = thisWeek.sessions === 0 && previousWeek.sessions === 0;
  const direction: LoadDirection = idle ? "none" : laps > 0 ? "up" : laps < 0 ? "down" : "same";
  return { laps, sessions, direction };
}

/** "+12" / "−5" / "±0", with a true minus sign. */
export function signed(value: number): string {
  return `${value > 0 ? "+" : value < 0 ? "−" : "±"}${Math.abs(value)}`;
}
