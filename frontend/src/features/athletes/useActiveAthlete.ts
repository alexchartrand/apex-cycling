import { useEffect } from "react";
import { useAthleteScope } from "./athleteScope";
import { setViewingAthleteId, useViewingAthleteId } from "./viewing";
import { useAthlete, useMyAthlete } from "./useAthlete";

/**
 * The athlete whose data the current screen shows: the signed-in user's own,
 * unless a coach is looking at one of their athletes (`/coach/athletes/:id`)
 * or they picked another through the athlete switcher (an admin a roster or
 * managed athlete). Every page reads its athlete through this hook.
 */
export function useActiveAthlete() {
  const me = useMyAthlete();
  const scope = useAthleteScope();
  const viewingId = useViewingAthleteId();
  const viewed = useAthlete(scope?.athleteId ?? viewingId ?? "");

  // Access ended (link revoked, athlete deleted): fall back to my own data
  // instead of leaving every page on a 403.
  const lostAccess = !scope && viewingId !== null && viewed.isError;
  useEffect(() => {
    if (lostAccess) setViewingAthleteId(null);
  }, [lostAccess]);

  if (scope) return viewed;
  if (viewingId === null || lostAccess) return me;
  return viewed;
}

/** `viewing` is the other athlete being shown, or undefined when it's my own data. */
export function useViewingOther() {
  const me = useMyAthlete();
  const active = useActiveAthlete();
  const other = me.data && active.data && active.data.id !== me.data.id ? active.data : undefined;
  return { viewing: other, stopViewing: () => setViewingAthleteId(null) };
}
