import { ROLLOUT_PRESETS, type Bike, type Gear } from "./types";

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

/** Bikes whose weight is known: the only ones that can stand in for a typed bike weight. */
export function weighedBikes(bikes: Bike[]): (Bike & { weight_kg: number })[] {
  return bikes.filter((bike): bike is Bike & { weight_kg: number } => bike.weight_kg != null);
}

/** The first bike of that weight, so a picker shows which bike a typed value is; null for none or no value. */
export function bikeOfWeight(bikes: Bike[], weightKg: number | null): Bike | null {
  if (weightKg == null) return null;
  return bikes.find((bike) => bike.weight_kg != null && Math.abs(bike.weight_kg - weightKg) < 0.005) ?? null;
}

/** The saved gear with these teeth and rollout (to the millimetre); null when none matches. */
export function gearOf(bikes: Bike[], chainring: number | null, cog: number | null, rolloutMm: number | null): Gear | null {
  if (chainring == null || cog == null || rolloutMm == null) return null;
  for (const bike of bikes) {
    const gear = bike.gears.find(
      (g) => g.chainring_teeth === chainring && g.cog_teeth === cog && Math.abs(g.rollout_mm - rolloutMm) < 0.5,
    );
    if (gear) return gear;
  }
  return null;
}

/** The standard tire whose rollout this is (to the millimetre); null for a measured or custom value. */
export function rolloutPresetOf(rolloutMm: number | null): (typeof ROLLOUT_PRESETS)[number] | null {
  if (rolloutMm == null) return null;
  return ROLLOUT_PRESETS.find((preset) => Math.abs(preset.rolloutMm - rolloutMm) < 0.5) ?? null;
}
