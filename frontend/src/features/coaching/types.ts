export type CoachLinkStatus = "pending_athlete_acceptance" | "pending_coach_acceptance" | "active" | "revoked";

/** One coach–athlete link as the signed-in user sees it. */
export interface CoachLink {
  id: string;
  status: CoachLinkStatus;
  athlete_id: string;
  athlete_name: string;
  coach_user_id: string;
  coach_name: string | null;
  initiated_by_me: boolean;
  /** A pending request that is mine to accept or decline. */
  needs_my_response: boolean;
  created_at: string;
  responded_at: string | null;
}

/** Ask for a link as the coach, or as the athlete (side). The other person: an id from a shared club, or an email. */
export type CoachLinkRequest =
  | { acting_as: "coach"; athlete_id: string }
  | { acting_as: "coach"; athlete_email: string }
  | { acting_as: "athlete"; athlete_id?: string; coach_user_id: string }
  | { acting_as: "athlete"; athlete_id?: string; coach_email: string };

export interface WeekLoad {
  sessions: number;
  laps: number;
  avg_rpe: number | null;
}

export interface AthleteCard {
  athlete_id: string;
  athlete_name: string;
  last_session: { external_event_id: string; name: string; event_date: string; lap_count: number } | null;
  this_week: WeekLoad;
  previous_week: WeekLoad;
  new_records: number;
  failing_transponders: string[];
  unread_comments: number;
}

/** Sessions with comments from other people I haven't read yet. */
export interface CommentInboxItem {
  athlete_id: string;
  athlete_name: string;
  external_event_id: string;
  event_name: string;
  event_date: string;
  unread_count: number;
  latest_at: string;
  latest_author_name: string | null;
  latest_excerpt: string;
}
