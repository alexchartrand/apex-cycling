import type { StartType } from "../training/types";

export type Priority = "A" | "B" | "C";
export type RacePhase = "past" | "race_day" | "taper" | "build";

export interface Season {
  id: string;
  name: string;
  start_date: string;
  /** The day before the next season starts; null for the latest. */
  end_date: string | null;
  is_current: boolean;
}

export interface SeasonBest {
  place: string;
  track_id: string | null;
  event_key: string;
  start_type: StartType;
  time_ms: number;
  achieved_on: string;
  source: "sqorz" | "manual";
  external_event_id: string | null;
  /** The best before the season began; null for a first result there. */
  previous_best_ms: number | null;
  improved: boolean;
}

export interface SeasonSummary {
  season: Season;
  sessions: number;
  races: number;
  bests: SeasonBest[];
}

export interface SeasonWrite {
  name: string;
  start_date: string;
}

export interface CompetitionGoal {
  id: string;
  event_key: string;
  start_type: StartType;
  target_time_ms: number;
}

export interface Competition {
  id: string;
  name: string;
  competition_date: string;
  priority: Priority;
  location: string | null;
  notes: string | null;
  goal: CompetitionGoal | null;
  days_until: number;
  taper_starts_on: string | null;
  /** Days until the taper begins (club time zone); null when there is none or it has begun. */
  days_to_taper: number | null;
  phase: RacePhase;
  /** The session of that day marked as a race. */
  race_session_id: string | null;
}

export interface CompetitionWrite {
  name: string;
  competition_date: string;
  priority: Priority;
  location: string | null;
  notes: string | null;
  goal_id: string | null;
}

export interface CalendarFeedStatus {
  enabled: boolean;
  /** Only in the answer that made the link. */
  url: string | null;
}
