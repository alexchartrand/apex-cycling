import { SearchX } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { EmptyState, PageHeader, SkeletonGroup } from "../components/ui";
import { RecordingActions } from "../features/activities/RecordingActions";
import { RecordingView } from "../features/activities/RecordingView";
import { useActivity } from "../features/activities/useActivities";
import { useActiveAthlete, useViewingOther } from "../features/athletes/useActiveAthlete";
import { useFormat } from "../i18n/useFormat";
import "./ActivityPage.css";

/** A ride on its own. One linked to a sqorz session lives on that session's Ride tab instead. */
export function ActivityPage() {
  const { t } = useTranslation(["activities", "shell", "common"]);
  const fmt = useFormat();
  const navigate = useNavigate();
  const { activityId = "" } = useParams();
  const athlete = useActiveAthlete().data;
  const { viewing } = useViewingOther();
  const athleteId = athlete?.id ?? "";
  // A coach reads; the athlete (or a club admin for a managed athlete) edits.
  const canEdit = !viewing || viewing.user_id === null;

  const activity = useActivity(athleteId, activityId);
  const notFound = activity.error instanceof ApiError && activity.error.status === 404;
  const data = activity.data;

  if (notFound) {
    return (
      <>
        <PageHeader title={t("activity.notFound")} back={{ to: "/log", label: t("activity.back") }} />
        <EmptyState icon={<SearchX aria-hidden />} title={t("activity.notFound")} />
      </>
    );
  }

  if (data?.external_event_id) {
    return <Navigate replace to={`/sessions/${encodeURIComponent(data.external_event_id)}?tab=ride&recording=${encodeURIComponent(data.id)}`} />;
  }

  const start = data ? new Date(data.start_time) : null;
  const title = data ? (data.name ?? t("untitled", { date: fmt.date(start, "medium") })) : "";

  return (
    <div className="activity-page">
      <PageHeader
        back={{ to: "/log", label: t("activity.back") }}
        eyebrow={start ? `${fmt.date(start, "long")} · ${fmt.time(start)}` : undefined}
        title={title || <SkeletonGroup lines={1} />}
        description={data ? t(`sources.${data.source}`) : undefined}
        actions={data && <RecordingActions athleteId={athleteId} activity={data} canEdit={canEdit} onDeleted={() => navigate("/log")} />}
      />

      {activity.isLoading && <SkeletonGroup lines={6} />}
      {activity.isError && !notFound && <p role="alert">{t("activity.loadError")}</p>}

      {data && <RecordingView athleteId={athleteId} activity={data} canEdit={canEdit} />}
    </div>
  );
}
