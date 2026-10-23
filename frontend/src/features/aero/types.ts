/** What an estimate assumes; null takes the default (track, profile, physics). */
export interface AeroInputs {
  temp_c: number | null;
  elevation_m: number | null;
  pressure_hpa: number | null;
  humidity_pct: number | null;
  rider_kg: number | null;
  /** Bike, shoes, helmet and skinsuit. */
  bike_kg: number | null;
  crr: number | null;
}

export interface AeroEstimateRequest extends Partial<AeroInputs> {
  track_id?: string | null;
  /** null = the automatic steady-lap pick. */
  lap_ids?: string[] | null;
}

export type AeroProblem = "no_track_length" | "no_weight" | "no_power" | "too_few_laps" | "implausible_fit";

export type AeroIssue = "excluded" | "no_power" | "first_lap" | "unsteady_speed" | "unsteady_power" | "too_slow";

export interface AeroConditions {
  temp_c: number;
  elevation_m: number;
  pressure_hpa: number | null;
  humidity_pct: number;
  rho: number;
  rider_kg: number | null;
  /** The profile entry the weight came from; null when it was typed in. */
  rider_kg_date: string | null;
  bike_kg: number;
  efficiency: number;
}

export interface AeroPoint {
  lap_id: string;
  start_time: string;
  effort_index: number;
  lap_in_effort: number;
  time_s: number;
  speed_ms: number;
  power_w: number | null;
  /** η·P/v less the speed gained: the resistive force the lap's power overcame. */
  resistance_n: number | null;
  cda_m2: number | null;
  issue: AeroIssue | null;
  used: boolean;
}

export interface AeroFit {
  cda_m2: number;
  crr: number;
  crr_source: "fitted" | "given" | "default";
  r_squared: number | null;
  cda_se_m2: number | null;
  laps_used: number;
  speed_ms: number;
  power_w: number;
  speed_spread: number;
}

export interface AeroTrackChoice {
  track_id: string;
  track_name: string;
  length_m: number | null;
  lap_count: number;
}

export interface AeroEstimate {
  external_event_id: string;
  event_name: string;
  event_date: string;
  track_id: string;
  track_name: string;
  track_length_m: number | null;
  tracks: AeroTrackChoice[];
  conditions: AeroConditions;
  points: AeroPoint[];
  fit: AeroFit | null;
  problem: AeroProblem | null;
}

export interface AeroSetup {
  label: string;
  position: string | null;
  helmet: string | null;
  skinsuit: string | null;
  bike: string | null;
  notes: string | null;
}

export interface AeroTestCreate extends Partial<AeroInputs>, AeroSetup {
  external_event_id: string;
  track_id?: string | null;
  lap_ids?: string[] | null;
}

export type AeroTestUpdate = Partial<AeroInputs> & Partial<AeroSetup> & { lap_ids?: string[] | null };

export interface AeroTest extends AeroSetup {
  id: string;
  external_event_id: string;
  event_name: string;
  event_date: string;
  track_id: string;
  track_name: string;
  lap_ids: string[] | null;
  inputs: AeroInputs;
  created_at: string;
  conditions: AeroConditions;
  fit: AeroFit | null;
  problem: AeroProblem | null;
}

export interface AeroTestDetail extends AeroTest {
  points: AeroPoint[];
}
