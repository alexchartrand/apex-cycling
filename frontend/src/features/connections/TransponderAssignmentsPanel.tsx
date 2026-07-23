import { useState } from "react";
import { ApiError } from "../../api/client";
import { useImportTransponderAssignmentNow, useReportTransponderUsage, useTransponderAssignments } from "./useConnections";

export function TransponderAssignmentsPanel({ athleteId }: { athleteId: string }) {
  const assignments = useTransponderAssignments(athleteId);
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
    </section>
  );
}
