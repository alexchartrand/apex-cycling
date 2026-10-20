export type WorkerState = "ok" | "stale" | "never";

export type WorkerStatus = {
  state: WorkerState;
  started_at: string | null;
  last_seen_at: string | null;
  last_poll_started_at: string | null;
  last_poll_finished_at: string | null;
  last_poll_connections: number | null;
  last_poll_failures: number | null;
  last_error: string | null;
};

export type AdminCounts = { users: number; athletes: number; clubs: number; active_transponders: number };

export type AdminUserRow = {
  id: string;
  email: string;
  display_name: string | null;
  created_at: string;
  is_active: boolean;
  is_platform_admin: boolean;
};

export type FailedRun = {
  id: string;
  transponder: string;
  requested_at: string;
  http_status: number | null;
  error_message: string | null;
};

export type AdminOverview = {
  worker: WorkerStatus;
  counts: AdminCounts;
  recent_users: AdminUserRow[];
  failed_runs: FailedRun[];
};
