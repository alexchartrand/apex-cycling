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
