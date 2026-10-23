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

export interface PlannedSession {
  id: string;
  planned_date: string;
  title: string;
  description: string | null;
  targets: PlannedEffort[];
  status: PlanStatus;
  created_by_name: string | null;
  /** The session that was ridden, when linked. */
  session: LinkedPlanSession | null;
  /** The author and the athlete's side edit the content. */
  can_edit: boolean;
  /** Only the athlete's side marks it done, skipped or linked. */
  can_mark: boolean;
}

export interface PlannedSessionWrite {
  planned_date: string;
  title: string;
  description: string | null;
  targets: PlannedEffort[];
}

export interface PlannedSessionUpdate {
  planned_date?: string;
  title?: string;
  description?: string | null;
  targets?: PlannedEffort[];
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

export interface PlanComparison {
  reps: RepResult[];
  /** Reps with a target time, and how many made it. */
  measured: number;
  hits: number;
}
