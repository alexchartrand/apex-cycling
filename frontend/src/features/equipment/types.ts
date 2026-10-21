export interface Gear {
  id: string;
  bike_id: string;
  chainring_teeth: number;
  cog_teeth: number;
  rollout_mm: number;
  tire: string | null;
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
}

/** Bounds mirror the backend's validation (`equipment/schemas.py`). */
export const GEAR_BOUNDS = {
  chainring: { min: 10, max: 100 },
  cog: { min: 5, max: 60 },
  rollout: { min: 1000, max: 3000 },
  bikeKg: { min: 3, max: 40 },
} as const;

/** A 700×25c track tire turns about this far, ridden. */
export const DEFAULT_ROLLOUT_MM = 2100;
