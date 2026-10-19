import { useMyAthlete } from "./useAthlete";

/**
 * The athlete whose data the current screen shows. Today that's always the
 * logged-in user's own athlete; the coach "view as athlete" switcher (T4.4)
 * will plug in here, so every page reads its athlete through this hook.
 */
export function useActiveAthlete() {
  return useMyAthlete();
}
