import type { ClubRole } from "./types";

export const CLUB_SECTIONS = ["members", "athletes", "leaderboard", "invites", "tracks", "settings"] as const;
export type ClubSection = (typeof CLUB_SECTIONS)[number];

/** Which sections a role gets: athletes see the club, coaches add the roster, admins run it. */
export function sectionsFor(role: ClubRole): ClubSection[] {
  if (role === "club_admin") return [...CLUB_SECTIONS];
  if (role === "coach") return ["members", "athletes", "leaderboard", "tracks"];
  return ["members", "leaderboard", "tracks"];
}
