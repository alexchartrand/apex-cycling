/** Backend `training_plans/schemas.py`. */

export type Sport = "cycling" | "track_cycling";
export const SPORTS: Sport[] = ["cycling", "track_cycling"];

export type PhaseKind = "base" | "build" | "peak" | "taper" | "race" | "recovery" | "transition";
export const PHASE_KINDS: PhaseKind[] = ["base", "build", "peak", "taper", "race", "recovery", "transition"];

export type PlanAuthor = "athlete" | "coach" | "ai";
export type PlanState = "upcoming" | "active" | "finished";

/** A stretch of the plan with one purpose, `start` to `end` inclusive (YYYY-MM-DD). */
export interface Phase {
  kind: PhaseKind;
  name?: string | null;
  start: string;
  end: string;
  focus?: string | null;
  hours?: number | null;
}

/** A week of the plan not yet written session by session. */
export interface OutlineWeek {
  week_start: string;
  focus: string;
  hours?: number | null;
  notes?: string | null;
}

export interface PlanGoal {
  id: string;
  event_key: string;
  start_type: "standing" | "flying";
  target_time_ms: number;
  target_date: string;
}

export interface PlanRace {
  id: string;
  name: string;
  date: string;
  priority: string;
}

export interface ProgressWeek {
  week_start: string;
  /** Not skipped. */
  sessions: number;
  done_sessions: number;
  planned_s: number;
  planned_tss: number | null;
  /** What the done sessions took, from their linked recording or sqorz session. */
  done_s: number;
  done_tss: number | null;
}

export interface PlanProgress {
  done: number;
  skipped: number;
  /** Still planned once their day has passed. */
  missed: number;
  /** Still planned, today or later: what deleting the plan removes. */
  upcoming: number;
  compliance: number | null;
  weeks: ProgressWeek[];
}

export interface TrainingPlan {
  id: string;
  name: string;
  sport: Sport;
  start_date: string;
  end_date: string;
  goal_text: string | null;
  goal_date: string | null;
  goal: PlanGoal | null;
  race: PlanRace | null;
  hours_per_week: number | null;
  phases: Phase[];
  weeks: OutlineWeek[];
  /** Index into `phases` of the one today falls in. */
  current_phase: number | null;
  state: PlanState;
  author: PlanAuthor;
  created_by_name: string | null;
  can_edit: boolean;
  progress: PlanProgress;
}

export interface TrainingPlanWrite {
  name: string;
  sport: Sport;
  start_date: string;
  end_date: string;
  goal_text: string | null;
  goal_date: string | null;
  goal_id: string | null;
  competition_id: string | null;
  hours_per_week: number | null;
  phases: Phase[];
  weeks?: OutlineWeek[];
}
