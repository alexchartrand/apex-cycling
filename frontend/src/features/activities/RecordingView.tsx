import { useTranslation } from "react-i18next";
import { Badge, Card, SkeletonGroup } from "../../components/ui";
import { ActivityNotes } from "./ActivityNotes";
import { ActivityStats } from "./ActivityStats";
import { CurveChart } from "./CurveChart";
import { compareCurves } from "./powerCurve";
import type { SessionOverlay } from "./sessionOverlay";
import { SessionLinkPanel } from "./SessionLinkPanel";
import { StreamChart } from "./StreamChart";
import type { Activity } from "./types";
import { useActivityAnalysis, useActivityStreams } from "./useActivities";
import { ZoneBars } from "./ZoneBars";
import "./Activities.css";

/**
 * Everything about one recording: stats, the streams, zones, its power curve,
 * the sqorz link and the athlete's notes. Shown on the ride's own page and on
 * the Ride tab of the session it is linked to, which shows the streams on its
 * Overview instead (`streams={false}`).
 */
export function RecordingView({
  athleteId,
  activity,
  canEdit,
  streams = true,
}: {
  athleteId: string;
  activity: Activity;
  canEdit: boolean;
  streams?: boolean;
}) {
  const { t } = useTranslation("activities");
  const analysis = useActivityAnalysis(athleteId, activity.id);

  const power = analysis.data;
  const curveRows = power ? compareCurves(power.power_curve.map((p) => ({ ...p, activity_id: activity.id, start_time: "" })), []) : [];

  return (
    <div className="recording-view">
      {activity.source === "strava" && <Badge tone="accent">{t("sourceOnly.strava")}</Badge>}
      <ActivityStats activity={activity} analysis={power} />
      {activity.has_power && power && power.ftp_w == null && <p className="ui-card__hint">{t("activity.hints.noFtp")}</p>}

      {streams && <RecordingStreams athleteId={athleteId} activityId={activity.id} />}

      {power && (
        <div className="recording-view__zones">
          {power.power_zones ? (
            <ZoneBars kind="power" zones={power.power_zones} unit="W" />
          ) : (
            activity.has_power && (
              <Card title={t("activity.zones.power")}>
                <p className="ui-card__hint">{t("activity.zones.needFtp")}</p>
              </Card>
            )
          )}
          {power.hr_zones ? (
            <ZoneBars kind="hr" zones={power.hr_zones} unit="bpm" />
          ) : (
            activity.has_heart_rate && (
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

      <div className="recording-view__side">
        <SessionLinkPanel athleteId={athleteId} activity={activity} canEdit={canEdit} />
        {canEdit && <ActivityNotes key={`${activity.id}-${activity.rpe}-${activity.name}-${activity.notes}`} athleteId={athleteId} activity={activity} />}
      </div>
    </div>
  );
}

/** A recording's streams chart, loading its samples; `session` lays a linked session over it. */
export function RecordingStreams({ athleteId, activityId, session }: { athleteId: string; activityId: string; session?: SessionOverlay }) {
  const streams = useActivityStreams(athleteId, activityId);
  if (streams.isLoading) return <SkeletonGroup lines={5} />;
  return streams.data ? <StreamChart streams={streams.data} session={session} /> : null;
}
