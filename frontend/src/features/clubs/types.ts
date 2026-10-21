export type ClubRole = "athlete" | "coach" | "club_admin";

/** What an invite link may grant. */
export type InviteRole = "athlete" | "coach";

export interface Club {
  id: string;
  name: string;
  slug: string;
  timezone: string;
  /** The signed-in user's role in it. */
  role: ClubRole;
}

export interface Member {
  id: string;
  user_id: string;
  role: ClubRole;
  display_name: string | null;
  athlete_id: string | null;
  /** Only sent to club admins. */
  email: string | null;
  joined_at: string;
}

export interface RosterAthlete {
  id: string;
  display_name: string;
  user_id: string | null;
  /** No login: the club's admins run this profile. */
  managed: boolean;
  birthdate: string | null;
  sex: "female" | "male" | null;
}

export interface ManagedAthletePayload {
  display_name: string;
  birthdate?: string | null;
  sex?: "female" | "male" | null;
  height_cm?: number | null;
}

export interface Invite {
  id: string;
  role: ClubRole;
  expires_at: string;
  max_uses: number | null;
  use_count: number;
  email: string | null;
  created_at: string;
}

/** Returned once on creation: only its hash is stored, so the link can't be shown again. */
export interface InviteCreated extends Invite {
  url: string;
  emailed: boolean;
}

export interface InvitePayload {
  role: InviteRole;
  expires_in_days: number;
  max_uses: number | null;
  email?: string;
  locale?: "fr" | "en";
}

export interface InvitePreview {
  club_name: string;
  role: ClubRole;
  already_member: boolean;
}

export interface SqorzAccount {
  sqorz_account_id: string;
  track_names: string[];
}

export interface LeaderboardEntry {
  rank: number;
  display_name: string;
  time_ms: number;
  achieved_on: string;
  sex: "female" | "male" | null;
  /** UCI age category code as of today; null without a birthdate. */
  category: string | null;
  source: "sqorz" | "manual";
  is_me: boolean;
}

/** The best time of each athlete who opted in, on one track, for one event and start. */
export interface Leaderboard {
  event_key: string;
  start_type: "standing" | "flying";
  track_id: string;
  track_name: string;
  /** Opted-in athletes on the roster, with or without a time here. */
  participants: number;
  /** Age categories among the unfiltered entries, youngest first. */
  categories: string[];
  entries: LeaderboardEntry[];
}

export interface LeaderboardQuery {
  eventKey: string;
  startType: "standing" | "flying";
  trackId: string;
  sex: "" | "female" | "male";
  category: string;
}
