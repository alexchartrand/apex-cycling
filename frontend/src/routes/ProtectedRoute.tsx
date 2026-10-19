import { Navigate, Outlet, useLocation } from "react-router-dom";
import { BrandMark } from "../brand/BrandMark";
import { useCurrentUser } from "../features/auth/useAuth";

export function ProtectedRoute() {
  const { data: user, isLoading } = useCurrentUser();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="boot-splash" role="status" aria-label="Loading">
        <BrandMark size={56} />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <Outlet />;
}
