import type { PowerProfile } from "./types";

/** Days of power the profile looks at. */
export const PROFILE_DAYS = 90;

const dismissedKey = (athleteId: string) => `ftp-suggestion-dismissed:${athleteId}`;

/** The suggestion as a whole number of watts, which is what gets saved. */
export function suggestedFtp(profile: PowerProfile | undefined): number | null {
  return profile?.ftp_suggestion ? Math.round(profile.ftp_suggestion.ftp_w) : null;
}

/** "Not now" is remembered per rider and per value, so a changed suggestion asks again. */
export function isDismissed(athleteId: string, watts: number): boolean {
  try {
    return localStorage.getItem(dismissedKey(athleteId)) === String(watts);
  } catch {
    return false;
  }
}

export function dismiss(athleteId: string, watts: number): void {
  try {
    localStorage.setItem(dismissedKey(athleteId), String(watts));
  } catch {
    // Storage can be blocked; the prompt then simply comes back next time.
  }
}

/** Joules of anaerobic work capacity (W′) as kilojoules. */
export function wPrimeKj(joules: number): number {
  return joules / 1000;
}

/** Whether the fit is a line worth showing: it needs a decent R² over enough efforts. */
export function fitIsTrustworthy(profile: PowerProfile | undefined): boolean {
  const fit = profile?.critical_power;
  return !!fit && fit.r_squared >= 0.98 && fit.points >= 3;
}
