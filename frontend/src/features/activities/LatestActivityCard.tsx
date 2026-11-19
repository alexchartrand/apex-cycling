import { ArrowRight, Clock, Gauge, Route, Zap } from "lucide-react";
import { useTranslation } from "react-i18next";
import { ButtonLink, Card, StatTile } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { useAthletePath } from "../athletes/athleteScope";
import { TypeBadge } from "./TypeBadge";
import { useActivitiesRange } from "./useActivities";

/**
 * The newest recording, whatever the sport (ride, gym session, later a run):
 * its type, time, distance and load. Nothing until there is one.
 */
export function LatestActivityCard({ athleteId }: { athleteId: string }) {
  const { t } = useTranslation(["activities", "home"]);
  const fmt = useFormat();
  const path = useAthletePath();
  const latest = useActivitiesRange(athleteId, { limit: 1 }).data?.[0];
  if (!latest) return null;

  const title = latest.name ?? t(`types.${latest.activity_type}.untitled`, { date: fmt.date(latest.start_time, "medium") });
  const seconds = latest.moving_s ?? latest.elapsed_s;

  return (
    <Card
      as="section"
      className="latest-activity"
      eyebrow={`${t("home:latestActivity.eyebrow")} · ${fmt.date(latest.start_time, "weekday")}`}
      title={title}
      actions={
        <ButtonLink to={path(`/activities/${latest.id}`)} size="sm" variant="secondary" iconRight={<ArrowRight aria-hidden />}>
          {t("home:latest.open")}
        </ButtonLink>
      }
    >
      <div>
        <TypeBadge type={latest.activity_type} />
      </div>
      <div className="latest-activity__stats">
        <StatTile
          label={t("home:latestActivity.time")}
          icon={<Clock aria-hidden />}
          value={seconds >= 3600 ? fmt.duration(seconds) : Math.round(seconds / 60)}
          unit={seconds >= 3600 ? "h" : "min"}
        />
        {latest.distance_m != null && latest.distance_m > 0 && (
          <StatTile label={t("home:latestActivity.distance")} icon={<Route aria-hidden />} value={fmt.distance(latest.distance_m)} />
        )}
        {latest.avg_power_w != null && (
          <StatTile label={t("home:latestActivity.power")} icon={<Zap aria-hidden />} value={Math.round(latest.avg_power_w)} unit="W" />
        )}
        {latest.tss != null && (
          <StatTile label={t("home:latestActivity.load")} icon={<Gauge aria-hidden />} value={Math.round(latest.tss)} unit="TSS" />
        )}
      </div>
    </Card>
  );
}
