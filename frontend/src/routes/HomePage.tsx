import { useCurrentUser } from "../features/auth/useAuth";

export function HomePage() {
  const { data: user } = useCurrentUser();

  return (
    <div>
      <h1>Welcome{user?.email ? `, ${user.email}` : ""}</h1>
      <p>Use the sidebar to import your training data, browse sessions, or track your progress over time.</p>
    </div>
  );
}
