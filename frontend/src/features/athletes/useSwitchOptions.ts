import { useMyClubs, useRosters } from "../clubs/useClubs";
import { buildSwitchOptions, type SwitchOption } from "./switchOptions";
import { useMyAthlete } from "./useAthlete";

/** Everyone whose data the signed-in user can switch to (see `buildSwitchOptions`), and whether that list is still loading. */
export function useSwitchOptionsState(): { options: SwitchOption[]; loading: boolean } {
  const me = useMyAthlete();
  const clubs = useMyClubs();
  const adminClubs = (clubs.data ?? []).filter((club) => club.role === "club_admin");
  const rosters = useRosters(adminClubs.map((club) => club.id));

  return {
    options: buildSwitchOptions({
      me: me.data ? { id: me.data.id, name: me.data.display_name } : undefined,
      rosters: adminClubs.map((club, index) => ({ clubName: club.name, athletes: rosters[index]?.data ?? [] })),
    }),
    loading: me.isLoading || clubs.isLoading || rosters.some((roster) => roster.isLoading),
  };
}

export function useSwitchOptions(): SwitchOption[] {
  return useSwitchOptionsState().options;
}
