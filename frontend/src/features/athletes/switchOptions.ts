export type SwitchGroup = "me" | "club";

export interface SwitchOption {
  athleteId: string;
  name: string;
  group: SwitchGroup;
  /** The club it comes from, for the "club" group. */
  clubName?: string;
}

interface SwitchSources {
  me: { id: string; name: string } | undefined;
  /** The rosters of the clubs the user administers. */
  rosters: { clubName: string; athletes: { id: string; display_name: string }[] }[];
}

const byName = (a: SwitchOption, b: SwitchOption) => a.name.localeCompare(b.name);

/**
 * Whose data the user can switch to: themself first, then the rosters of the
 * clubs they administer. An athlete on several rosters is listed once. The
 * athletes a coach coaches aren't here: a coach reads them under
 * `/coach/athletes/:id`, never as a switch.
 */
export function buildSwitchOptions({ me, rosters }: SwitchSources): SwitchOption[] {
  const options: SwitchOption[] = [];
  const seen = new Set<string>();
  const add = (option: SwitchOption) => {
    if (seen.has(option.athleteId)) return;
    seen.add(option.athleteId);
    options.push(option);
  };

  if (me) add({ athleteId: me.id, name: me.name, group: "me" });
  for (const roster of rosters) {
    roster.athletes
      .map((athlete) => ({ athleteId: athlete.id, name: athlete.display_name, group: "club" as const, clubName: roster.clubName }))
      .sort(byName)
      .forEach(add);
  }
  return options;
}
