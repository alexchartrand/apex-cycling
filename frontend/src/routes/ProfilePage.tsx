import { useMyAthlete } from "../features/athletes/useAthlete";
import { useCurrentUser } from "../features/auth/useAuth";

export function ProfilePage() {
  const { data: user } = useCurrentUser();
  const athlete = useMyAthlete();

  return (
    <div>
      <h1>Profile</h1>
      {athlete.isLoading && <p>Loading…</p>}
      {athlete.isError && <p role="alert">Could not load your athlete profile. Try reloading the page.</p>}
      {athlete.data && (
        <dl>
          <dt>Name</dt>
          <dd>{athlete.data.display_name}</dd>
          <dt>Email</dt>
          <dd>{user?.email}</dd>
        </dl>
      )}
    </div>
  );
}
