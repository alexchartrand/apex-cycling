export interface Athlete {
  id: string;
  user_id: string | null;
  club_id: string | null;
  display_name: string;
  birthdate: string | null;
  sex: Sex | null;
  height_cm: number | null;
  /** UCI age category code (U11…U23, ELITE, M30, M35…), from the birthdate. */
  category: string | null;
  /** Whether the athlete's best times show on their club's leaderboard (their own choice). */
  leaderboard_opt_in: boolean;
}

export type Sex = "female" | "male";

export interface AthleteUpdate {
  display_name?: string;
  birthdate?: string | null;
  sex?: Sex | null;
  height_cm?: number | null;
  /** Only the athlete (or a club admin for a managed athlete) may change this. */
  leaderboard_opt_in?: boolean;
}

export const METRIC_FIELDS = ["weight_kg", "ftp_w", "max_hr", "resting_hr"] as const;
export type MetricField = (typeof METRIC_FIELDS)[number];

/** One dated measurement; any subset of the values may be recorded. */
export type AthleteMetric = { id: string; effective_date: string } & Record<MetricField, number | null>;

export type AthleteMetricPayload = { effective_date: string } & Partial<Record<MetricField, number>>;

export interface DatedValue {
  value: number;
  effective_date: string;
}

/** Each value as of `on`: the latest recorded on or before it, with its date. */
export type CurrentMetrics = { on: string } & Record<MetricField, DatedValue | null>;
