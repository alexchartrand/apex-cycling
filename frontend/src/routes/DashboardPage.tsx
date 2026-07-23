import { Link } from "react-router-dom";
import { useMyAthlete } from "../features/athletes/useAthlete";
import { useLogout, useCurrentUser } from "../features/auth/useAuth";
import { TransponderAssignmentsPanel } from "../features/connections/TransponderAssignmentsPanel";

export function DashboardPage() {
  const { data: user } = useCurrentUser();
  const logout = useLogout();
  const athlete = useMyAthlete();

  return (
    <div>
      <h1>Track Trainer</h1>
      <p>Signed in as {user?.email}</p>
      <button onClick={() => logout.mutate()} disabled={logout.isPending}>
        Log out
      </button>
      <nav>
        <Link to="/sessions">Sessions</Link> · <Link to="/progression">Progression</Link>
      </nav>
      {athlete.data && <TransponderAssignmentsPanel athleteId={athlete.data.id} />}
    </div>
  );
}
