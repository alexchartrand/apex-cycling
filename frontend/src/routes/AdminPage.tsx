import { useTranslation } from "react-i18next";
import { Navigate } from "react-router-dom";
import { PageHeader, SkeletonGroup } from "../components/ui";
import { AdminOverviewPanel } from "../features/admin/AdminOverview";
import { useCurrentUser } from "../features/auth/useAuth";

/** Platform-admin status page: worker health, failed syncs and the newest accounts. */
export function AdminPage() {
  const { t } = useTranslation("admin");
  const { data: user, isLoading } = useCurrentUser();

  if (isLoading) return <SkeletonGroup lines={4} />;
  if (!user?.is_platform_admin) return <Navigate to="/" replace />;

  return (
    <>
      <PageHeader title={t("title")} description={t("description")} />
      <AdminOverviewPanel />
    </>
  );
}
