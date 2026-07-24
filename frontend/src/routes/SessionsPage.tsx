import { Link } from "react-router-dom";
import { useMyAthlete } from "../features/athletes/useAthlete";
import { useSessions } from "../features/training/useTraining";

export function SessionsPage() {
  const athlete = useMyAthlete();
  const sessions = useSessions(athlete.data?.id ?? "");

  return (
    <div>
      <h1>Sessions</h1>
      {sessions.isLoading && <p>Loading…</p>}
      {sessions.isError && <p role="alert">Could not load your sessions. Try reloading the page.</p>}
      {sessions.data && sessions.data.length === 0 && (
        <p>No sessions yet. Report a transponder on the Import page to start syncing your training data.</p>
      )}
      {sessions.data && sessions.data.length > 0 && (
        <ul>
          {sessions.data.map((session) => (
            <li key={session.external_event_id}>
              <Link to={`/sessions/${session.external_event_id}`}>
                {session.event_date} — {session.event_name}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
