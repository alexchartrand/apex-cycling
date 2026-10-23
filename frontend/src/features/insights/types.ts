import type { StartType } from "../training/types";

export type InsightKind = "personal_record" | "season_best" | "best_nth_lap" | "most_consistent";

/** A headline about a session (backend `InsightRead`); which fields are set depends on `kind`. */
export interface Insight {
  /** Stable across refetches: one per session, track, kind and subject. */
  key: string;
  kind: InsightKind;
  external_event_id: string;
  session_name: string;
  event_date: string;
  track_id: string;
  track_name: string;
  event_key: string | null;
  start_type: StartType | null;
  time_ms: number | null;
  previous_ms: number | null;
  /** personal_record only: the round time this was the first to get under. */
  milestone_ms: number | null;
  lap_number: number | null;
  lap_count: number | null;
  cv_pct: number | null;
  effort_start_type: StartType | null;
  first_lap_id: string | null;
}
