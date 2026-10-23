export type ActivitySource = "upload" | "intervals_icu" | "strava";

export interface Activity {
  id: string;
  athlete_id: string;
  source: ActivitySource;
  name: string | null;
  sport: string | null;
  start_time: string;
  elapsed_s: number;
  moving_s: number | null;
  distance_m: number | null;
  elevation_gain_m: number | null;
  has_power: boolean;
  has_heart_rate: boolean;
  has_cadence: boolean;
  avg_power_w: number | null;
  max_power_w: number | null;
  normalized_power_w: number | null;
  tss: number | null;
  avg_heart_rate: number | null;
  max_heart_rate: number | null;
  avg_cadence: number | null;
  avg_speed_mps: number | null;
  notes: string | null;
  rpe: number | null;
  file_format: string | null;
  created_at: string;
  /** The sqorz session this ride contains, if linked. */
  external_event_id: string | null;
  /** Where the ride lives at its source (Strava requires linking back). */
  external_url: string | null;
  /** Seconds added to the device's clock to get sqorz time. */
  clock_offset_s: number;
  session_link_manual: boolean;
}

export type UploadStatus = "created" | "duplicate" | "failed";

export interface UploadResult {
  filename: string;
  status: UploadStatus;
  activity: Activity | null;
  error: string | null;
}

export interface ActivityUpdate {
  name?: string | null;
  notes?: string | null;
  rpe?: number | null;
}

export interface ActivityStreams {
  sample_count: number;
  point_count: number;
  time_s: (number | null)[];
  power_w: (number | null)[] | null;
  heart_rate: (number | null)[] | null;
  cadence: (number | null)[] | null;
  speed_mps: (number | null)[] | null;
  distance_m: (number | null)[] | null;
  altitude_m: (number | null)[] | null;
}

export interface ZoneDistribution {
  limits: number[];
  seconds: number[];
}

export interface ActivityAnalysis {
  ftp_w: number | null;
  weight_kg: number | null;
  max_hr: number | null;
  intensity_factor: number | null;
  variability_index: number | null;
  avg_power_w_per_kg: number | null;
  normalized_power_w_per_kg: number | null;
  work_kj: number | null;
  power_zones: ZoneDistribution | null;
  hr_zones: ZoneDistribution | null;
  power_curve: { duration_s: number; power_w: number }[];
}

export interface SessionSuggestion {
  external_event_id: string | null;
  event_name: string | null;
  clock_offset_s: number | null;
  correlation: number | null;
  margin: number | null;
  laps_used: number | null;
  confident: boolean;
}

export interface PowerCurvePoint {
  duration_s: number;
  power_w: number;
  activity_id: string;
  start_time: string;
}

export interface CriticalPower {
  cp_w: number;
  w_prime_j: number;
  r_squared: number;
  /** Efforts between 3 and 20 minutes the line went through. */
  points: number;
}

export interface FtpSuggestion {
  ftp_w: number;
  source_duration_s: number;
  source_activity_id: string;
  source_power_w: number;
}

/** What the recent power says about threshold; each part is null when the data can't support it. */
export interface PowerProfile {
  days: number;
  critical_power: CriticalPower | null;
  ftp_current_w: number | null;
  ftp_suggestion: FtpSuggestion | null;
}

export interface TrainingLoadDay {
  day: string;
  tss: number;
  ctl: number;
  atl: number;
  tsb: number;
}

export interface TrainingLoad {
  days: TrainingLoadDay[];
  unrated_activities: number;
}

export type RunStatus = "pending" | "success" | "failed";

export interface SyncRun {
  status: RunStatus;
  requested_at: string;
  completed_at: string | null;
  error_message: string | null;
  imported_count: number | null;
}

export interface IntervalsStatus {
  connected: boolean;
  active: boolean;
  intervals_athlete_id: string | null;
  intervals_athlete_name: string | null;
  last_synced_at: string | null;
  runs: SyncRun[];
}

export interface StravaStatus {
  available: boolean;
  connected: boolean;
  active: boolean;
  strava_athlete_name: string | null;
  last_synced_at: string | null;
  runs: SyncRun[];
}
