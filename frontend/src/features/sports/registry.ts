import { Bike, Dumbbell, Gauge, type LucideIcon } from "lucide-react";
import type { ActivityType } from "../activities/types";

/**
 * The sports an athlete does (`Athlete.sports`, the backend's
 * `kinds.ATHLETE_SPORTS`). Coarser than activity types: indoor rides are
 * cycling. They decide which sport-specific pages and Home cards the app
 * shows; pages every sport shares (Log, Plans, Fitness, Season…) aren't
 * listed here and are always shown.
 *
 * Adding a sport (running): add it to `kinds.ATHLETE_SPORTS` and here, with
 * its activity types, the pages and cards only it needs, and its intensity.
 */
export type Sport = "track_cycling" | "cycling" | "strength";

/** Pages only some sports need (keys of `NAV_ITEMS`). */
export type SportPage = "records" | "power" | "aero" | "equipment" | "tools";

/** Home cards only some sports need. */
export type SportCard = "track";

export interface SportDef {
  key: Sport;
  icon: LucideIcon;
  /** The activity types that count as this sport. */
  activityTypes: readonly ActivityType[];
  pages: readonly SportPage[];
  homeCards: readonly SportCard[];
  /** How effort is measured: power targets, pace (running), or neither (RPE only). */
  intensity: "power" | "pace" | "rpe";
}

export const SPORT_DEFS: Record<Sport, SportDef> = {
  track_cycling: {
    key: "track_cycling",
    icon: Gauge,
    activityTypes: ["track_cycling"],
    pages: ["records", "power", "aero", "equipment", "tools"],
    homeCards: ["track"],
    intensity: "power",
  },
  cycling: {
    key: "cycling",
    icon: Bike,
    activityTypes: ["cycling", "indoor_cycling"],
    pages: ["power", "aero", "equipment"],
    homeCards: [],
    intensity: "power",
  },
  strength: {
    key: "strength",
    icon: Dumbbell,
    activityTypes: ["strength"],
    pages: [],
    homeCards: [],
    intensity: "rpe",
  },
};

/** In the order settings list them (the backend stores them in this order too). */
export const SPORTS: readonly Sport[] = ["track_cycling", "cycling", "strength"];

const GATED_PAGES = new Set<string>(SPORTS.flatMap((sport) => SPORT_DEFS[sport].pages));

export function isSport(value: string): value is Sport {
  return (SPORTS as readonly string[]).includes(value);
}

/** Whether a page is shown to someone doing these sports: shared pages always are. */
export function pageShown(page: string, sports: ReadonlySet<Sport>): boolean {
  if (!GATED_PAGES.has(page)) return true;
  return [...sports].some((sport) => (SPORT_DEFS[sport].pages as readonly string[]).includes(page));
}

export function cardShown(card: SportCard, sports: ReadonlySet<Sport>): boolean {
  return [...sports].some((sport) => SPORT_DEFS[sport].homeCards.includes(card));
}

/** The sport an activity type belongs to; null for "other". */
export function sportOfType(type: ActivityType): Sport | null {
  return SPORTS.find((sport) => SPORT_DEFS[sport].activityTypes.includes(type)) ?? null;
}

/**
 * The sports of an athlete who hasn't chosen: what their data shows (a
 * transponder or a velodrome ridden = track; the kinds of training recorded),
 * or every sport when there is nothing yet, so a new account sees the whole
 * app rather than an empty one.
 */
export function guessSports(evidence: { hasTrack: boolean; activityTypes: Iterable<ActivityType> }): Set<Sport> {
  const found = new Set<Sport>();
  if (evidence.hasTrack) found.add("track_cycling");
  for (const type of evidence.activityTypes) {
    const sport = sportOfType(type);
    if (sport) found.add(sport);
  }
  return found.size > 0 ? found : new Set(SPORTS);
}

/** The athlete's sports: their choice, else the guess. */
export function resolveSports(chosen: readonly string[] | null | undefined, guess: () => Set<Sport>): Set<Sport> {
  const valid = (chosen ?? []).filter(isSport);
  return valid.length > 0 ? new Set(valid) : guess();
}
