import type { CadenceTarget, PowerTarget, StepKind, WorkoutEstimate, WorkoutItem } from "../workouts/types";

export type PlanStatus = "planned" | "done" | "skipped";

export interface PlannedEffort {
  label: string;
  reps: number;
  event_key: string | null;
  start_type: "standing" | "flying" | null;
  target_time_ms: number | null;
  /** One of the athlete's gears to ride it in. */
  gear_setup_id: string | null;
  /** "Track bike · 50×15", sent back by the server only. */
  gear_label?: string | null;
}

export interface LinkedPlanSession {
  external_event_id: string;
  event_name: string;
  event_date: string;
}

/** A recording of the ride (head unit, trainer). */
export interface LinkedRecording {
  id: string;
  name: string | null;
  start_time: string;
}

/** A gear the workout asks for (as teeth), found among the athlete's saved gears. */
export interface PlanWorkoutGear {
  chainring_teeth: number;
  cog_teeth: number;
  gear_setup_id: string;
  /** "Track bike · 50×15" */
  label: string;
}

export interface PlannedSession {
  id: string;
  planned_date: string;
  title: string;
  description: string | null;
  /** The older free-form plan; new plans carry a `workout` instead. */
  targets: PlannedEffort[];
  /** The plan's own copy of a workout's steps, taken when it was scheduled. */
  workout: WorkoutItem[] | null;
  /** With the athlete's FTP on the planned date. */
  workout_estimate: WorkoutEstimate | null;
  workout_gears: PlanWorkoutGear[];
  /** The library workout it was copied from, while the viewer can still open it. */
  source_workout_id: string | null;
  status: PlanStatus;
  created_by_name: string | null;
  /** The session that was ridden, when linked. */
  session: LinkedPlanSession | null;
  /** The recording linked to the plan itself, while the viewer may see it (a Strava ride is its owner's only). */
  activity: LinkedRecording | null;
  /** The author and the athlete's side edit the content. */
  can_edit: boolean;
  /** Only the athlete's side marks it done, skipped or linked. */
  can_mark: boolean;
  /** Its copy on the athlete's Intervals.icu calendar, when they push plans there. */
  intervals: "pending" | "sent" | "failed" | null;
}

export interface PlannedSessionWrite {
  planned_date: string;
  title: string;
  description: string | null;
  targets: PlannedEffort[];
  workout: WorkoutItem[] | null;
  source_workout_id: string | null;
}

export interface PlannedSessionUpdate {
  planned_date?: string;
  title?: string;
  description?: string | null;
  targets?: PlannedEffort[];
  /** Null removes it, and its source with it. */
  workout?: WorkoutItem[] | null;
  source_workout_id?: string | null;
  status?: PlanStatus;
}

/** How the ridden session answered one rep of the plan (backend `planning/matching.py`). */
export type RepStatus = "hit" | "miss" | "ridden" | "not_ridden" | "free";

export interface RepResult {
  target_index: number;
  rep: number;
  label: string;
  event_key: string | null;
  target_time_ms: number | null;
  status: RepStatus;
  /** The effort of the session that answers it (its number in the efforts list). */
  effort_index: number | null;
  start_type: "standing" | "flying" | null;
  time_ms: number | null;
  /** time − target; negative = faster. */
  delta_ms: number | null;
}

/** How the recording answered one power or cadence target (backend `planning/power_matching.py`). */
export type StepStatus = "hit" | "under" | "over" | "not_ridden" | "unmeasured";

export interface StepResult {
  /** Position in riding order, repeats unrolled (0-based). */
  step_index: number;
  kind: StepKind;
  label: string | null;
  power: PowerTarget | null;
  cadence: CadenceTarget | null;
  /** The power target in watts (% FTP with the FTP on the planned date). */
  power_low_w: number | null;
  power_high_w: number | null;
  /** Where it was found, in seconds from the start of the recording. */
  start_s: number | null;
  end_s: number | null;
  avg_power_w: number | null;
  avg_cadence: number | null;
  /** Null when the step has no target of that kind. */
  power_status: StepStatus | null;
  cadence_status: StepStatus | null;
}

export interface PlanComparison {
  /** Track efforts against the linked session. */
  reps: RepResult[];
  /** Reps with a target time, and how many made it. */
  measured: number;
  hits: number;
  /** The recording the power steps were read from: the plan's own, else the session's. */
  recording: LinkedRecording | null;
  steps: StepResult[];
  /** Steps with a power target that could be measured, and how many were on target. */
  power_measured: number;
  power_hits: number;
}
