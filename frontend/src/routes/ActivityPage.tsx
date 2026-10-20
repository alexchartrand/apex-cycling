import { useState } from "react";
import { ExternalLink, SearchX, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { errorMessage } from "../api/errors";
import { Badge, Button, Card, ConfirmDialog, EmptyState, PageHeader, SkeletonGroup, useToast } from "../components/ui";
import { ActivityNotes } from "../features/activities/ActivityNotes";
import { ActivityStats } from "../features/activities/ActivityStats";
import { CurveChart } from "../features/activities/CurveChart";
import { SessionLinkPanel } from "../features/activities/SessionLinkPanel";
import { StreamChart } from "../features/activities/StreamChart";
import { compareCurves } from "../features/activities/powerCurve";
import {
  useActivity,
  useActivityAnalysis,
  useActivityStreams,
  useDeleteActivity,
} from "../features/activities/useActivities";
import { ZoneBars } from "../features/activities/ZoneBars";
import { useActiveAthlete, useViewingOther } from "../features/athletes/useActiveAthlete";
import { useFormat } from "../i18n/useFormat";
import "../features/activities/Activities.css";
import "./ActivityPage.css";

export function ActivityPage() {
  const { t } = useTranslation(["activities", "shell", "common"]);
  const fmt = useFormat();
  const navigate = useNavigate();
  const { toast } = useToast();
  const { activityId = "" } = useParams();
  const athlete = useActiveAthlete().data;
  const { viewing } = useViewingOther();
  const athleteId = athlete?.id ?? "";
  // A coach reads; the athlete (or a club admin for a managed athlete) edits.
  const canEdit = !viewing || viewing.user_id === null;

  const activity = useActivity(athleteId, activityId);
  const analysis = useActivityAnalysis(athleteId, activityId);
  const streams = useActivityStreams(athleteId, activityId);
  const remove = useDeleteActivity(athleteId);
  const [confirming, setConfirming] = useState(false);

  const notFound = activity.error instanceof ApiError && activity.error.status === 404;
  const data = activity.data;

  async function handleDelete() {
    try {
      await remove.mutateAsync(activityId);
      toast({ title: t("activity.delete.deleted") });
      navigate("/log");
    } catch (err) {
      toast({ title: errorMessage(err), tone: "error" });
      throw err;
    }
  }

  if (notFound) {
    return (
      <>
        <PageHeader title={t("activity.notFound")} back={{ to: "/log", label: t("activity.back") }} />
        <EmptyState icon={<SearchX aria-hidden />} title={t("activity.notFound")} />
      </>
    );
  }

  const start = data ? new Date(data.start_time) : null;
  const title = data ? (data.name ?? t("untitled", { date: fmt.date(start, "medium") })) : "";
  const power = analysis.data;
  const curveRows = power ? compareCurves(power.power_curve.map((p) => ({ ...p, activity_id: activityId, start_time: "" })), []) : [];

  return (
    <div className="activity-page">
      <PageHeader
        back={{ to: "/log", label: t("activity.back") }}
        eyebrow={start ? `${fmt.date(start, "long")} · ${fmt.time(start)}` : undefined}
        title={title || <SkeletonGroup lines={1} />}
        description={data ? t(`sources.${data.source}`) : undefined}
        actions={
          data && (
            <>
              {data.external_url && (
                <a className="btn btn--secondary btn--md" href={data.external_url} target="_blank" rel="noreferrer">
                  <ExternalLink aria-hidden />
                  <span className="btn__label">{data.source === "strava" ? t("activity.viewOnStrava") : t("activity.viewOnIntervals")}</span>
                </a>
              )}
              {canEdit && (
                <Button variant="ghost" icon={<Trash2 aria-hidden />} onClick={() => setConfirming(true)}>
                  {t("activity.delete.action")}
                </Button>
              )}
            </>
          )
        }
      />

      {activity.isLoading && <SkeletonGroup lines={6} />}
      {activity.isError && !notFound && <p role="alert">{t("activity.loadError")}</p>}

      {data && (
        <>
          {data.source === "strava" && <Badge tone="accent">{t("sourceOnly.strava")}</Badge>}
          <ActivityStats activity={data} analysis={power} />
          {data.has_power && power && power.ftp_w == null && <p className="ui-card__hint">{t("activity.hints.noFtp")}</p>}

          {streams.data && <StreamChart streams={streams.data} />}
          {streams.isLoading && <SkeletonGroup lines={5} />}

          {power && (
            <div className="activity-page__zones">
              {power.power_zones ? (
                <ZoneBars kind="power" zones={power.power_zones} unit="W" />
              ) : (
                data.has_power && (
                  <Card title={t("activity.zones.power")}>
                    <p className="ui-card__hint">{t("activity.zones.needFtp")}</p>
                  </Card>
                )
              )}
              {power.hr_zones ? (
                <ZoneBars kind="hr" zones={power.hr_zones} unit="bpm" />
              ) : (
                data.has_heart_rate && (
                  <Card title={t("activity.zones.hr")}>
                    <p className="ui-card__hint">{t("activity.zones.needMaxHr")}</p>
                  </Card>
                )
              )}
            </div>
          )}

          {curveRows.length > 0 && (
            <Card title={t("activity.curve.title")}>
              <p className="ui-card__hint">{t("activity.curve.description")}</p>
              <CurveChart rows={curveRows} unit="W" seriesA={t("activity.curve.title")} emptyMessage={t("power.empty")} />
            </Card>
          )}

          <div className="activity-page__side">
            <SessionLinkPanel athleteId={athleteId} activity={data} canEdit={canEdit} />
            {canEdit && <ActivityNotes key={`${data.id}-${data.rpe}-${data.name}-${data.notes}`} athleteId={athleteId} activity={data} />}
          </div>
        </>
      )}

      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={t("activity.delete.title")}
        description={t("activity.delete.description")}
        confirmLabel={t("activity.delete.action")}
        cancelLabel={t("common:cancel")}
        tone="danger"
        onConfirm={handleDelete}
      />
    </div>
  );
}
