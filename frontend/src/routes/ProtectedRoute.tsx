import { Navigate, Outlet } from "react-router-dom";
import { useCurrentUser } from "../features/auth/useAuth";

export function ProtectedRoute() {
  const { data: user, isLoading } = useCurrentUser();

  if (isLoading) {
    return <p>Loading…</p>;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
