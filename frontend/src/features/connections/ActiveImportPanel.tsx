import { useState } from "react";
import { ApiError } from "../../api/client";
import { Button } from "../../components/ui";
import { useStopTransponderAssignment, useTransponderAssignments } from "./useConnections";

export function ActiveImportPanel({ athleteId }: { athleteId: string }) {
  const assignments = useTransponderAssignments(athleteId);
  const stopAssignment = useStopTransponderAssignment(athleteId);
  const [error, setError] = useState<string | null>(null);

  const activeAssignments = assignments.data?.filter((a) => a.end_date === null) ?? [];

  async function handleStop(assignmentId: string) {
    setError(null);
    try {
      await stopAssignment.mutateAsync(assignmentId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to stop import");
    }
  }

  return (
    <div className="import-panel">
      <section>
        <h2>Active imports</h2>
        {assignments.isLoading && <p>Loading…</p>}
        {assignments.isError && <p role="alert">Could not load active imports.</p>}
        {error && <p role="alert">{error}</p>}
        {assignments.data && activeAssignments.length === 0 && (
          <p>No imports are currently running. Enable Autoimport on the Sqorz tab to start one.</p>
        )}
        {activeAssignments.length > 0 && (
          <ul>
            {activeAssignments.map((assignment) => (
              <li key={assignment.id}>
                {assignment.transponder_code} — syncing since {assignment.start_date}{" "}
                <Button
                  scale="sm"
                  type="button"
                  onClick={() => handleStop(assignment.id)}
                  disabled={stopAssignment.isPending}
                >
                  Stop
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
