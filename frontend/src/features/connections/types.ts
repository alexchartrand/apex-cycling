export interface TransponderAssignment {
  id: string;
  athlete_id: string;
  transponder_code: string;
  start_date: string;
  end_date: string | null;
  notes: string | null;
  created_at: string;
}

export interface ReportUsagePayload {
  transponder_code: string;
  start_date: string;
  end_date?: string | null;
  notes?: string | null;
  import_now?: boolean;
}

export type IngestionRunStatus = "pending" | "success" | "failed";

export interface IngestionRun {
  id: string;
  status: IngestionRunStatus;
  requested_at: string;
  completed_at: string | null;
  http_status: number | null;
  error_message: string | null;
}

export interface IngestionRunWithSource extends IngestionRun {
  transponder_code: string;
}
