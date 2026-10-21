import type { StartType } from "../training/types";

export type PredictionProblem = "no_track" | "no_track_length" | "no_weight" | "no_power" | "no_cda";

export interface GoalBest {
  time_ms: number;
  achieved_on: string;
  place: string;
  track_id: string | null;
}

export interface GoalPrediction {
  time_ms: number;
  /** The best average power it assumes, over `power_duration_s`, set on `power_on`. */
  power_w: number;
  power_duration_s: number;
  power_on: string;
  cda_m2: number;
  cda_label: string;
  rider_kg: number;
}

export interface Goal {
  id: string;
  event_key: string;
  start_type: StartType;
  track_id: string | null;
  track_name: string | null;
  target_time_ms: number;
  target_date: string;
  notes: string | null;
  baseline_ms: number | null;
  created_at: string;
  best: GoalBest | null;
  /** Best minus target: positive while to go, zero or negative once reached. */
  gap_ms: number | null;
  achieved: boolean;
  /** 0..1 from the best when the goal was set to the target; null without a start or a best. */
  progress: number | null;
  days_left: number;
  prediction: GoalPrediction | null;
  prediction_problem: PredictionProblem | null;
}

export interface GoalCreate {
  event_key: string;
  start_type: "standing" | "flying";
  target_time_ms: number;
  target_date: string;
  track_id: string | null;
  notes: string | null;
}

/** PATCH body: the event and its start are fixed once set. */
export interface GoalUpdate {
  target_time_ms?: number;
  target_date?: string;
  track_id?: string | null;
  notes?: string | null;
}
