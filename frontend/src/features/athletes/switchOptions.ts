export type SwitchGroup = "me" | "coached" | "club";

export interface SwitchOption {
  athleteId: string;
  name: string;
  group: SwitchGroup;
  /** The club it comes from, for the "club" group. */
  clubName?: string;
}

interface SwitchSources {
  me: { id: string; name: string } | undefined;
  /** Coach links; only the active ones give access. */
  coached: { athlete_id: string; athlete_name: string; status: string }[];
  /** The rosters of the clubs the user administers. */
  rosters: { clubName: string; athletes: { id: string; display_name: string }[] }[];
}

const byName = (a: SwitchOption, b: SwitchOption) => a.name.localeCompare(b.name);

/**
 * Whose data the user can switch to: themself first, then the athletes they
 * coach, then the rosters of the clubs they administer. An athlete reachable
 * several ways is listed once, under the first way.
 */
export function buildSwitchOptions({ me, coached, rosters }: SwitchSources): SwitchOption[] {
  const options: SwitchOption[] = [];
  const seen = new Set<string>();
  const add = (option: SwitchOption) => {
    if (seen.has(option.athleteId)) return;
    seen.add(option.athleteId);
    options.push(option);
  };

  if (me) add({ athleteId: me.id, name: me.name, group: "me" });
  coached
    .filter((link) => link.status === "active")
    .map((link) => ({ athleteId: link.athlete_id, name: link.athlete_name, group: "coached" as const }))
    .sort(byName)
    .forEach(add);
  for (const roster of rosters) {
    roster.athletes
      .map((athlete) => ({ athleteId: athlete.id, name: athlete.display_name, group: "club" as const, clubName: roster.clubName }))
      .sort(byName)
      .forEach(add);
  }
  return options;
}
