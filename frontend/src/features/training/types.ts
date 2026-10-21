export interface SessionSummary {
  external_event_id: string;
  /** The title to show: the athlete's own, else sqorz's. */
  event_name: string;
  event_date: string;
  lap_count: number;
  track_names: string[];
  rpe: number | null;
  tags: string[];
  first_lap_at: string | null;
  last_lap_at: string | null;
}

export interface SegmentDetail {
  sequence_index: number;
  loop_id: string;
  loop_name: string;
  /** This split's own duration (not cumulative). */
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
  /** Left out of bests, records and charts (the athlete's choice). */
  excluded: boolean;
  label: string | null;
  segments: SegmentDetail[];
  views: ViewTime[];
  /** From a linked recording (head unit, power meter) over this lap. */
  avg_power_w?: number | null;
  avg_heart_rate?: number | null;
  avg_cadence?: number | null;
  /** What the session's gear implies at this lap's speed. */
  est_cadence_rpm?: number | null;
}

export interface LinkedActivity {
  id: string;
  name: string | null;
  start_time: string;
  elapsed_s: number;
  clock_offset_s: number;
  has_power: boolean;
  has_heart_rate: boolean;
  has_cadence: boolean;
}

export interface TrackSessionDetail {
  track_id: string;
  track_name: string;
  laps: LapDetail[];
}

export interface SessionDetail {
  external_event_id: string;
  /** The title to show: `title_override` if set, else `original_name`. */
  event_name: string;
  original_name: string;
  title_override: string | null;
  event_date: string;
  notes: string | null;
  rpe: number | null;
  tags: string[];
  tracks: TrackSessionDetail[];
  /** Recordings linked to this session. */
  activities?: LinkedActivity[];
  /** The gear ridden by default in this session. */
  gear_setup_id?: string | null;
}

/** PATCH body: fields left out are unchanged; null (or blank) clears one. */
export interface SessionUpdate {
  title_override?: string | null;
  notes?: string | null;
  rpe?: number | null;
  tags?: string[] | null;
}

export interface SessionMeta {
  external_event_id: string;
  event_name: string;
  original_name: string;
  title_override: string | null;
  notes: string | null;
  rpe: number | null;
  tags: string[];
}

export interface LapUpdate {
  excluded?: boolean;
  label?: string | null;
}

export type StartType = "standing" | "flying" | "unknown";

export interface HalfLapSplit {
  index: number;
  from_line: string;
  to_line: string;
  time_ms: number | null;
}

/** One continuous block of laps (see backend `efforts.py`). */
export interface Effort {
  index: number;
  track_id: string;
  track_name: string;
  label: string | null;
  start_time: string;
  start_type: StartType;
  lap_ids: string[];
  completed_lap_count: number;
  /** One per lap in `lap_ids`; null for an unfinished lap. */
  lap_times_ms: (number | null)[];
  total_time_ms: number | null;
  best_lap_ms: number | null;
  distance_m: number | null;
  avg_speed_kmh: number | null;
  half_lap_splits: HalfLapSplit[];
  avg_power_w?: number | null;
  avg_heart_rate?: number | null;
  avg_cadence?: number | null;
  /** This effort's own gear; null = the session's. */
  gear_setup_id?: string | null;
  est_cadence_rpm?: number | null;
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
  /** Only for whole-lap distances on a track with a known length. */
  start_type?: "standing" | "flying";
  from?: string;
  to?: string;
}
