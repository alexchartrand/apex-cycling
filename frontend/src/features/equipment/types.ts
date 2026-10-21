export interface Gear {
  id: string;
  bike_id: string;
  chainring_teeth: number;
  cog_teeth: number;
  rollout_mm: number;
  tire: string | null;
  crr: number | null;
  ratio: number;
  development_m: number;
  gear_inches: number;
}

export interface Bike {
  id: string;
  name: string;
  weight_kg: number | null;
  notes: string | null;
  gears: Gear[];
}

export interface BikePayload {
  name?: string;
  weight_kg?: number | null;
  notes?: string | null;
}

export interface GearPayload {
  chainring_teeth?: number;
  cog_teeth?: number;
  rollout_mm?: number;
  tire?: string | null;
  crr?: number | null;
}

/** Bounds mirror the backend's validation (`equipment/schemas.py`). */
export const GEAR_BOUNDS = {
  chainring: { min: 10, max: 100 },
  cog: { min: 5, max: 60 },
  rollout: { min: 1000, max: 3000 },
  bikeKg: { min: 3, max: 40 },
  crr: { min: 0.001, max: 0.02 },
} as const;

/** A new gear starts on the 700×23c preset. */
export const DEFAULT_ROLLOUT_MM = 2096;

/** Standard wheel circumferences (bike-computer tables, unloaded) offered next to every rollout field. */
export const ROLLOUT_PRESETS = [
  { tire: "700×21c", rolloutMm: 2090 },
  { tire: "700×23c", rolloutMm: 2096 },
  { tire: "700×25c", rolloutMm: 2105 },
  { tire: "700×28c", rolloutMm: 2136 },
] as const;

/** One entry of `tires.json`. */
export interface TireEntry {
  brand: string;
  name: string;
  /** e.g. tubular, clincher, tubeless. */
  type: string;
  /** Width in millimetres. */
  size: number;
  crr: number;
}

export interface StandardTire extends TireEntry {
  /** "Vittoria Pista Control tubular 23 mm": what picking it writes into the gear's tire. */
  label: string;
}
