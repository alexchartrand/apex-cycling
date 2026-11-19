import { useMemo } from "react";
import { useWeeklyLoad } from "../activities/useActivities";
import type { Athlete } from "../athletes/types";
import { useActiveAthlete } from "../athletes/useActiveAthlete";
import { useTransponderAssignments } from "../connections/useConnections";
import { useTracks } from "../training/useTraining";
import { guessSports, resolveSports, type Sport } from "./registry";

/** Weeks of training the guess looks at. */
const GUESS_WEEKS = 26;

/**
 * The active athlete's sports (so a coach view follows the athlete's): their
 * choice in Settings, else guessed from their data. `chosen` is false while
 * it's a guess.
 */
export function useMySports(): { sports: ReadonlySet<Sport>; chosen: boolean } {
  return useAthleteSports(useActiveAthlete().data);
}

/** One athlete's sports, for a screen outside their scope (the coach view's own tabs). */
export function useAthleteSports(athlete: Athlete | undefined): { sports: ReadonlySet<Sport>; chosen: boolean } {
  const chosen = (athlete?.sports?.length ?? 0) > 0;
  // Only asked when there's no choice to go by.
  const guessFrom = chosen || !athlete ? "" : athlete.id;
  const tracks = useTracks(guessFrom);
  const assignments = useTransponderAssignments(guessFrom);
  const load = useWeeklyLoad(guessFrom, GUESS_WEEKS);

  const sports = useMemo(
    () =>
      resolveSports(athlete?.sports, () =>
        guessSports({
          hasTrack: (tracks.data?.length ?? 0) > 0 || (assignments.data?.length ?? 0) > 0,
          activityTypes: (load.data ?? []).flatMap((week) => week.types.map((type) => type.activity_type)),
        }),
      ),
    [athlete?.sports, tracks.data, assignments.data, load.data],
  );
  return { sports, chosen };
}
