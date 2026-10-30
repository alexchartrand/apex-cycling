import type { StandardEventKey } from "../records/types";

/** Mirrors backend `workouts/schemas.py`. */
export type StepKind = "warmup" | "work" | "recovery" | "cooldown";
export const STEP_KINDS: StepKind[] = ["warmup", "work", "recovery", "cooldown"];

export type WorkoutSource = "mine" | "coach" | "preset";

export interface PowerTarget {
  unit: "ftp_pct" | "watts";
  low: number;
  /** Null for a single value. */
  high: number | null;
}

export interface CadenceTarget {
  low: number;
  high: number | null;
}

/** Teeth only: a library workout belongs to no athlete, so it can't name a saved gear. */
export interface GearRatio {
  chainring_teeth: number;
  cog_teeth: number;
}

/** At most one of duration/distance/laps; none = open (lap button), or the event's distance when it has one. */
export interface WorkoutStep {
  type?: "step";
  kind: StepKind;
  label: string | null;
  notes: string | null;
  duration_s: number | null;
  distance_m: number | null;
  laps: number | null;
  power: PowerTarget | null;
  cadence: CadenceTarget | null;
  rpe: number | null;
  event_key: StandardEventKey | null;
  start_type: "standing" | "flying" | null;
  target_time_ms: number | null;
  gear: GearRatio | null;
}

/** A repeat inside a repeat holds steps only: nesting stops at one level. */
export interface InnerRepeat {
  type: "repeat";
  count: number;
  steps: WorkoutStep[];
}

export interface RepeatBlock {
  type: "repeat";
  count: number;
  steps: (WorkoutStep | InnerRepeat)[];
}

export type WorkoutItem = WorkoutStep | RepeatBlock;

export interface ProfileSegment {
  start_s: number;
  duration_s: number;
  kind: StepKind;
  label: string | null;
  /** Fraction of FTP the estimate uses (from power, else the RPE); null = unrated. */
  intensity: number | null;
  power_low: number | null;
  power_high: number | null;
  is_track: boolean;
}

export interface WorkoutEstimate {
  /** Leaves out open steps (`open_steps` counts them). */
  duration_s: number;
  tss: number | null;
  unrated_s: number;
  open_steps: number;
  segments: ProfileSegment[];
}

export interface WorkoutSummary {
  id: string;
  source: WorkoutSource;
  name: string;
  description: string | null;
  tags: string[];
  is_track: boolean;
  duration_s: number;
  tss: number | null;
  owner_name: string | null;
  can_edit: boolean;
  created_at: string | null;
}

export interface Workout extends WorkoutSummary {
  steps: WorkoutItem[];
  estimate: WorkoutEstimate;
}

export interface WorkoutWrite {
  name: string;
  description: string | null;
  tags: string[];
  steps: WorkoutItem[];
}

export interface WorkoutFilters {
  q?: string;
  tag?: string;
  track?: boolean;
  source?: WorkoutSource;
  min_duration_s?: number;
  max_duration_s?: number;
}

export function isRepeat(item: WorkoutItem | InnerRepeat | WorkoutStep): item is RepeatBlock | InnerRepeat {
  return item.type === "repeat";
}

/** Watt targets need the athlete's FTP before they count in the estimate. */
export function hasWattTargets(items: (WorkoutItem | InnerRepeat)[]): boolean {
  return items.some((item) => (isRepeat(item) ? hasWattTargets(item.steps) : item.power?.unit === "watts"));
}

/** A step with a standard event: something the timing can score once the session is linked. */
export function hasTrackEvents(items: (WorkoutItem | InnerRepeat)[]): boolean {
  return items.some((item) => (isRepeat(item) ? hasTrackEvents(item.steps) : item.event_key != null));
}

/** "50×15": how a gear is written, and the key a plan's matched gear labels use. */
export const gearKey = (chainring: number, cog: number) => `${chainring}×${cog}`;
