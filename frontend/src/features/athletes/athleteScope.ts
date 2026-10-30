import { createContext, useContext } from "react";

/**
 * A coach looking at one of their athletes, under `/coach/athletes/:id`. The
 * athlete pages render inside it read-only: the coach reads, comments and
 * plans, nothing else. Outside it (own data, a club admin's switch) there is
 * no scope.
 */
export interface AthleteScope {
  athleteId: string;
  basePath: string;
}

export const AthleteScopeContext = createContext<AthleteScope | null>(null);

export function coachAthletePath(athleteId: string, path = ""): string {
  return `/coach/athletes/${encodeURIComponent(athleteId)}${path}`;
}

export function useAthleteScope(): AthleteScope | null {
  return useContext(AthleteScopeContext);
}

/** Turns an athlete page's address (`/sessions/…`) into the one to link to here. */
export function useAthletePath(): (path: string) => string {
  const scope = useAthleteScope();
  return scope ? (path) => scope.basePath + path : (path) => path;
}

/** False while a coach looks at an athlete: their data is read-only. */
export function useCanEdit(): boolean {
  return useAthleteScope() === null;
}
