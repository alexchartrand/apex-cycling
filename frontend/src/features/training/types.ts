export interface SessionSummary {
  external_event_id: string;
  event_name: string;
  event_date: string;
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
}

export interface TrackLoopSummary {
  id: string;
  name: string;
  distance_m: number | null;
}

export interface TrackSummary {
  id: string;
  name: string;
  views: TrackViewSummary[];
  loops: TrackLoopSummary[];
  length_m: number | null;
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
