import { RefreshCw, WifiOff } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { BrandMark } from "../brand/BrandMark";
import { Button, EmptyState } from "../components/ui";
import { useCurrentUser } from "../features/auth/useAuth";

export function ProtectedRoute() {
  const { t } = useTranslation();
  const { data: user, isLoading, error, refetch, isFetching } = useCurrentUser();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="boot-splash" role="status" aria-label={t("loading")}>
        <BrandMark size={56} />
      </div>
    );
  }

  // Unreachable server and nothing cached: don't bounce to a login form
  // that can't work offline either.
  if (!user && error instanceof TypeError) {
    return (
      <div className="boot-splash">
        <EmptyState
          icon={<WifiOff aria-hidden />}
          title={t("offlineTitle")}
          description={t("networkError")}
          action={
            <Button icon={<RefreshCw aria-hidden />} loading={isFetching} onClick={() => refetch()}>
              {t("retry")}
            </Button>
          }
        />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <Outlet />;
}
