import { useState } from "react";
import { ApiError } from "../../api/client";
import { Button, Input } from "../../components/ui";
import {
  useImportTransponderAssignmentNow,
  useIngestionRuns,
  useReportTransponderUsage,
  useTransponderAssignments,
} from "./useConnections";

export function SqorzImportPanel({ athleteId }: { athleteId: string }) {
  const assignments = useTransponderAssignments(athleteId);
  const ingestionRuns = useIngestionRuns(athleteId);
  const reportUsage = useReportTransponderUsage(athleteId);
  const importNow = useImportTransponderAssignmentNow(athleteId);

  const [transponderCode, setTransponderCode] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [autoimport, setAutoimport] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastImportMessage, setLastImportMessage] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await reportUsage.mutateAsync({
        transponder_code: transponderCode,
        start_date: startDate,
        end_date: autoimport ? null : endDate || null,
      });
      setTransponderCode("");
      setStartDate("");
      setEndDate("");
      setAutoimport(false);
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
    <div className="import-panel">
      <section>
        <h2>Sqorz Data</h2>
        <form onSubmit={handleSubmit}>
          <Input
            scale="sm"
            label="Transponder code"
            value={transponderCode}
            onChange={(e) => setTransponderCode(e.target.value)}
            placeholder="XX-XXXXX"
            required
          />
          <Input
            scale="sm"
            type="date"
            label="Start date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            required
          />
          <label className="import-panel__checkbox-row">
            <input
              type="checkbox"
              checked={autoimport}
              onChange={(e) => {
                setAutoimport(e.target.checked);
                if (e.target.checked) setEndDate("");
              }}
            />
            Keep syncing
          </label>
          <Input
            scale="sm"
            type="date"
            label="End date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            disabled={autoimport}
          />
          {error && <p role="alert">{error}</p>}
          <Button scale="sm" type="submit" disabled={reportUsage.isPending}>
            {reportUsage.isPending ? "Saving…" : "Import"}
          </Button>
        </form>

        {lastImportMessage && <p>{lastImportMessage}</p>}
      </section>

      <section>
        <h2>Your assignments</h2>
        {assignments.isLoading && <p>Loading…</p>}
        {assignments.isError && <p role="alert">Could not load your transponder assignments.</p>}
        {assignments.data && assignments.data.length === 0 && <p>No transponder usage reported yet.</p>}
        {assignments.data && assignments.data.length > 0 && (
          <ul>
            {assignments.data.map((assignment) => (
              <li key={assignment.id}>
                {assignment.transponder_code}: {assignment.start_date} – {assignment.end_date ?? "ongoing"}{" "}
                <Button
                  scale="sm"
                  type="button"
                  onClick={() => handleImportNow(assignment.id)}
                  disabled={importNow.isPending}
                >
                  Import now
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
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
    </div>
  );
}
