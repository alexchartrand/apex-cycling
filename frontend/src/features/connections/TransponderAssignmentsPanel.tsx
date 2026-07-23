import { useState } from "react";
import { ApiError } from "../../api/client";
import {
  useImportTransponderAssignmentNow,
  useIngestionRuns,
  useReportTransponderUsage,
  useTransponderAssignments,
} from "./useConnections";

export function TransponderAssignmentsPanel({ athleteId }: { athleteId: string }) {
  const assignments = useTransponderAssignments(athleteId);
  const ingestionRuns = useIngestionRuns(athleteId);
  const reportUsage = useReportTransponderUsage(athleteId);
  const importNow = useImportTransponderAssignmentNow(athleteId);

  const [transponderCode, setTransponderCode] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [lastImportMessage, setLastImportMessage] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await reportUsage.mutateAsync({
        transponder_code: transponderCode,
        start_date: startDate,
        end_date: endDate || null,
      });
      setTransponderCode("");
      setStartDate("");
      setEndDate("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to report transponder usage");
    }
  }

  async function handleImportNow(assignmentId: string) {
    setLastImportMessage(null);
    try {
      const run = await importNow.mutateAsync(assignmentId);
      setLastImportMessage(
        run.status === "success" ? "Import succeeded." : `Import failed: ${run.error_message ?? "unknown error"}`,
      );
    } catch (err) {
      setLastImportMessage(err instanceof ApiError ? err.message : "Import failed");
    }
  }

  return (
    <section>
      <h2>Transponder usage</h2>
      <form onSubmit={handleSubmit}>
        <label>
          Transponder code
          <input
            value={transponderCode}
            onChange={(e) => setTransponderCode(e.target.value)}
            placeholder="LS-03407"
            required
          />
        </label>
        <label>
          Start date
          <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} required />
        </label>
        <label>
          End date (leave blank if ongoing)
          <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
        </label>
        {error && <p role="alert">{error}</p>}
        <button type="submit" disabled={reportUsage.isPending}>
          {reportUsage.isPending ? "Saving…" : "Report usage & sync"}
        </button>
      </form>

      {lastImportMessage && <p>{lastImportMessage}</p>}

      <h2>Your assignments</h2>
      {assignments.isLoading && <p>Loading…</p>}
      {assignments.isError && <p role="alert">Could not load your transponder assignments.</p>}
      {assignments.data && assignments.data.length === 0 && <p>No transponder usage reported yet.</p>}
      {assignments.data && assignments.data.length > 0 && (
        <ul>
          {assignments.data.map((assignment) => (
            <li key={assignment.id}>
              {assignment.transponder_code}: {assignment.start_date} – {assignment.end_date ?? "ongoing"}{" "}
              <button
                type="button"
                onClick={() => handleImportNow(assignment.id)}
                disabled={importNow.isPending}
              >
                Import now
              </button>
            </li>
          ))}
        </ul>
      )}

      <h2>Recent sync activity</h2>
      {ingestionRuns.isLoading && <p>Loading…</p>}
      {ingestionRuns.isError && <p role="alert">Could not load sync history.</p>}
      {ingestionRuns.data && ingestionRuns.data.length === 0 && (
        <p>No syncs yet — report a transponder above to trigger one.</p>
      )}
      {ingestionRuns.data && ingestionRuns.data.length > 0 && (
        <ul>
          {ingestionRuns.data.map((run) => (
            <li key={run.id}>
              {run.transponder_code} — {new Date(run.requested_at).toLocaleString()} —{" "}
              {run.status === "success" && "succeeded"}
              {run.status === "pending" && "in progress"}
              {run.status === "failed" && (
                <span role="alert">failed: {run.error_message ?? "unknown error"}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
