import type { StartType } from "../training/types";

/** The standard events records are kept for (mirrors backend `STANDARD_EVENTS`). */
export const STANDARD_EVENT_KEYS = ["f200", "lap", "500m", "750m", "1km", "2km", "3km", "4km"] as const;
export type StandardEventKey = (typeof STANDARD_EVENT_KEYS)[number];

/** A flying 200 or single lap is only ever flying; longer distances also have a standing start. */
export const EVENT_START_TYPES: Record<StandardEventKey, ("standing" | "flying")[]> = {
  f200: ["flying"],
  lap: ["flying"],
  "500m": ["standing", "flying"],
  "750m": ["standing", "flying"],
  "1km": ["standing", "flying"],
  "2km": ["standing", "flying"],
  "3km": ["standing", "flying"],
  "4km": ["standing", "flying"],
};

/** Distance of each event in metres; null = one lap of whatever track it's ridden on. */
export const EVENT_DISTANCE_M: Record<StandardEventKey, number | null> = {
  f200: 200,
  lap: null,
  "500m": 500,
  "750m": 750,
  "1km": 1000,
  "2km": 2000,
  "3km": 3000,
  "4km": 4000,
};

/** One line of the records board or of a record's history. */
export interface RecordEntry {
  /** The track's name, or the venue text of a manual result with no track. */
  place: string;
  track_id: string | null;
  event_key: string;
  start_type: StartType;
  time_ms: number;
  achieved_on: string;
  source: "sqorz" | "manual";
  is_competition: boolean;
  external_event_id: string | null;
  lap_id: string | null;
  manual_result_id: string | null;
}

export interface ManualResult {
  id: string;
  event_key: string;
  start_type: "standing" | "flying";
  time_ms: number;
  achieved_on: string;
  track_id: string | null;
  venue: string | null;
  place: string;
  is_competition: boolean;
  notes: string | null;
}

/** Either `track_id` or `venue` says where. */
export interface ManualResultPayload {
  event_key: StandardEventKey;
  start_type: "standing" | "flying";
  time_ms: number;
  achieved_on: string;
  track_id?: string | null;
  venue?: string | null;
  is_competition: boolean;
  notes?: string | null;
}

/** Which record's history to show: a track, or the venue text of a manual result. */
export interface RecordSelection {
  track_id: string | null;
  place: string;
  event_key: string;
  start_type: "standing" | "flying";
}
