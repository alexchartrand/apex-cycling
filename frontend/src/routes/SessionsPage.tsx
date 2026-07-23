import { Link } from "react-router-dom";
import { useMyAthlete } from "../features/athletes/useAthlete";
import { useSessions } from "../features/training/useTraining";

export function SessionsPage() {
  const athlete = useMyAthlete();
  const sessions = useSessions(athlete.data?.id ?? "");

  return (
    <div>
      <p>
        <Link to="/">← Dashboard</Link>
      </p>
      <h1>Sessions</h1>
      {sessions.isLoading && <p>Loading…</p>}
      {sessions.data && sessions.data.length === 0 && <p>No sessions yet.</p>}
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
