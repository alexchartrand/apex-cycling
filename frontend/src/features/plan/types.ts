export type PlanStatus = "planned" | "done" | "skipped";

export interface PlannedEffort {
  label: string;
  reps: number;
  event_key: string | null;
  start_type: "standing" | "flying" | null;
  target_time_ms: number | null;
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
