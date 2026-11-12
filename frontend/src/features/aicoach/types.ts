import type { WorkoutEstimate, WorkoutItem } from "../workouts/types";

export interface AiUsage {
  month_tokens: number;
  monthly_cap: number;
}

/** `available`: the server has a model. `enabled`: an admin turned it on. `can_use`: also consented (the athlete only). */
export interface AiAccess {
  available: boolean;
  enabled: boolean;
  consented: boolean;
  is_self: boolean;
  can_use: boolean;
  usage: AiUsage | null;
  provider: string;
  model: string;
}

/** Days are ISO weekdays, 1 = Monday. */
export interface CoachProfile {
  goal?: string | null;
  goal_date?: string | null;
  hours_per_week?: number | null;
  available_days?: number[];
  track_days?: number[];
  max_weekday_minutes?: number | null;
  max_weekend_minutes?: number | null;
  experience?: string | null;
  injuries?: string | null;
  gym?: boolean | null;
  gym_details?: string | null;
  indoor_trainer?: boolean | null;
  power_meter?: boolean | null;
  other?: string | null;
}

export interface CoachSettings {
  weekly_reports: boolean;
  report_weekday: number;
  report_hour: number;
}

export interface OutlineWeek {
  week_start: string;
  focus: string;
  hours?: number | null;
  notes?: string | null;
}

export interface CoachProfileRead {
  answers: CoachProfile;
  settings: CoachSettings;
  program: { goal?: string | null; accepted_at?: string; outline?: OutlineWeek[] } | null;
}

export type ProposalOp = "create" | "update" | "skip" | "delete";
export type ProposalStatus = "pending" | "accepted" | "rejected" | "superseded" | "expired";

export interface PlanSnapshot {
  planned_date: string;
  title: string;
  status: "planned" | "done" | "skipped";
  duration_s: number | null;
  tss: number | null;
}

export interface ProposalItem {
  op: ProposalOp;
  plan_id: string | null;
  before: PlanSnapshot | null;
  planned_date: string | null;
  title: string | null;
  description: string | null;
  workout_name: string | null;
  workout: WorkoutItem[] | null;
  estimate: WorkoutEstimate | null;
  reason: string | null;
  warnings: string[];
}

export interface ProposalWeek {
  week_start: string;
  sessions: number;
  duration_s: number;
  tss: number | null;
}

export interface Proposal {
  id: string;
  kind: "plan" | "adjustment" | "replan";
  status: ProposalStatus;
  summary: string;
  goal: string | null;
  created_at: string;
  expires_at: string;
  decided_at: string | null;
  conversation_id: string | null;
  items: ProposalItem[];
  weeks: ProposalWeek[];
  outline: OutlineWeek[];
  errors: string[];
  warnings: string[];
  can_decide: boolean;
}

export interface AiMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  proposal: Proposal | null;
}

export type ConversationKind = "chat" | "intake" | "report" | "replan";

export interface ConversationSummary {
  id: string;
  kind: ConversationKind;
  title: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface Conversation extends ConversationSummary {
  messages: AiMessage[];
}

export interface Turn {
  conversation_id: string;
  messages: AiMessage[];
}

export interface AiReport {
  id: string;
  kind: "weekly" | "on_demand";
  period_start: string;
  period_end: string;
  content: string;
  stats: ReportStats;
  created_at: string;
  conversation_id: string | null;
  proposal_id: string | null;
}

export interface ReportStats {
  plans?: { total: number; done: number; skipped: number; missed: number; planned_tss: number | null };
  actual_tss?: number;
  sessions?: number;
  hours?: number;
  avg_rpe?: number | null;
  ctl?: [number | null, number | null];
  tsb_end?: number | null;
}

export interface AdminAiRow {
  athlete_id: string;
  display_name: string;
  email: string;
  enabled: boolean;
  consented: boolean;
  approved_at: string | null;
  monthly_token_cap: number | null;
  month_tokens: number;
  month_cost_usd: number;
}

export interface AdminAiOverview {
  available: boolean;
  model: string;
  default_monthly_tokens: number;
  rows: AdminAiRow[];
  month_tokens: number;
  month_cost_usd: number;
}
