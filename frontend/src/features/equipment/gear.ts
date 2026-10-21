import type { Bike, Gear } from "./types";

/** "50×15", the way riders say a gear. */
export function gearName(gear: Pick<Gear, "chainring_teeth" | "cog_teeth">): string {
  return `${gear.chainring_teeth}×${gear.cog_teeth}`;
}

export type GearChoice = { id: string; label: string };

/** Every gear of every bike, as picker entries: "Track bike · 50×15". */
export function gearChoices(bikes: Bike[]): GearChoice[] {
  return bikes.flatMap((bike) => bike.gears.map((gear) => ({ id: gear.id, label: `${bike.name} · ${gearName(gear)}` })));
}

/** Rollout in mm from a measured value in either unit the field accepts; null if it isn't a number. */
export function parseNumber(text: string): number | null {
  const value = Number(text.trim().replace(",", "."));
  return text.trim() !== "" && Number.isFinite(value) ? value : null;
}
