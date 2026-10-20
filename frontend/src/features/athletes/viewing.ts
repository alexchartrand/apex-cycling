import { useSyncExternalStore } from "react";

/**
 * Whose data the app is showing when it isn't the signed-in user's own: a
 * coach "viewing as" one of their athletes, a club admin looking at a
 * managed athlete. Kept per browser tab (sessionStorage) so a reload stays
 * on the same athlete but a new tab, or the next person, starts as
 * themselves. `useActiveAthlete` is the only reader that matters.
 */
const STORAGE_KEY = "apex-viewing-athlete";

function readStored(): string | null {
  try {
    return sessionStorage.getItem(STORAGE_KEY);
  } catch {
    return null; // storage blocked: still works for the life of the page
  }
}

let current: string | null = readStored();
const listeners = new Set<() => void>();

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Show this athlete's data (null = back to my own). */
export function setViewingAthleteId(athleteId: string | null) {
  if (athleteId === current) return;
  current = athleteId;
  try {
    if (athleteId) sessionStorage.setItem(STORAGE_KEY, athleteId);
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // in-memory only
  }
  listeners.forEach((listener) => listener());
}

export function useViewingAthleteId(): string | null {
  return useSyncExternalStore(
    subscribe,
    () => current,
    () => null,
  );
}
