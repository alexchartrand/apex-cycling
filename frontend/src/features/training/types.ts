export interface SessionSummary {
  external_event_id: string;
  event_name: string;
  event_date: string;
  lap_count: number;
  track_names: string[];
  first_lap_at: string | null;
  last_lap_at: string | null;
}

export interface SegmentDetail {
  sequence_index: number;
  loop_name: string;
  time_ms: number | null;
}

export interface ViewTime {
  track_view_id: string;
  name: string;
  time_ms: number | null;
}

export interface LapDetail {
  lap_id: string;
  start_time: string;
  class_code: string | null;
  start_number: number | null;
  whole_lap_time_ms: number | null;
  segments: SegmentDetail[];
  views: ViewTime[];
}

export interface TrackSessionDetail {
  track_id: string;
  track_name: string;
  laps: LapDetail[];
}

export interface SessionDetail {
  external_event_id: string;
  event_name: string;
  event_date: string;
  tracks: TrackSessionDetail[];
}

export interface TrackViewSummary {
  id: string;
  name: string;
  /** Left out of view pickers (display only). */
  hidden: boolean;
}

export interface TrackLoopSummary {
  id: string;
  name: string;
  distance_m: number | null;
  /** Not drawn on the track diagram (display only). */
  hidden: boolean;
}

export interface TrackSummary {
  id: string;
  name: string;
  views: TrackViewSummary[];
  loops: TrackLoopSummary[];
  length_m: number | null;
  indoor: boolean | null;
  elevation_m: number | null;
  default_temp_c: number | null;
  /** Whether the signed-in user may change these settings. */
  can_edit: boolean;
}

/** Fields left out are unchanged; null clears a fact. The hidden lists are the full set to hide. */
export interface TrackUpdate {
  length_m?: number | null;
  indoor?: boolean | null;
  elevation_m?: number | null;
  default_temp_c?: number | null;
  hidden_loop_ids?: string[];
  hidden_view_ids?: string[];
}

export type ProgressionMetric = "view" | "lap_time" | "custom_distance";

export interface ProgressionPoint {
  external_event_id: string;
  event_date: string;
  best_lap_id: string;
  time_ms: number;
  achieved_distance_m: number | null;
}

export interface ProgressionParams {
  metric: ProgressionMetric;
  track_id?: string;
  track_view_id?: string;
  distance_m?: number;
  from?: string;
  to?: string;
}
