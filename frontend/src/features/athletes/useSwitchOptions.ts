import { useCoachedAthletes } from "../coaching/useCoaching";
import { useMyClubs, useRosters } from "../clubs/useClubs";
import { buildSwitchOptions, type SwitchOption } from "./switchOptions";
import { useMyAthlete } from "./useAthlete";

/** Everyone whose data the signed-in user can switch to (see `buildSwitchOptions`). */
export function useSwitchOptions(): SwitchOption[] {
  const me = useMyAthlete();
  const coached = useCoachedAthletes();
  const clubs = useMyClubs();
  const adminClubs = (clubs.data ?? []).filter((club) => club.role === "club_admin");
  const rosters = useRosters(adminClubs.map((club) => club.id));

  return buildSwitchOptions({
    me: me.data ? { id: me.data.id, name: me.data.display_name } : undefined,
    coached: coached.data ?? [],
    rosters: adminClubs.map((club, index) => ({ clubName: club.name, athletes: rosters[index]?.data ?? [] })),
  });
}
