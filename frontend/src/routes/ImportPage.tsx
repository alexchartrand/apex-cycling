import { useMyAthlete } from "../features/athletes/useAthlete";
import { TransponderAssignmentsPanel } from "../features/connections/TransponderAssignmentsPanel";

export function ImportPage() {
  const athlete = useMyAthlete();

  return (
    <div>
      <h1>Import</h1>
      {athlete.isLoading && <p>Loading…</p>}
      {athlete.isError && <p role="alert">Could not load your athlete profile. Try reloading the page.</p>}
      {athlete.data && <TransponderAssignmentsPanel athleteId={athlete.data.id} />}
    </div>
  );
}
