import { useMemo } from "react";
import { ArrowRight, CalendarDays, Clock, Flag, ListOrdered, Radio, Timer } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Badge, ButtonLink, Card, StatTile, type DeltaDirection } from "../../components/ui";
import { localIsoDate } from "../../i18n/format";
import { useFormat } from "../../i18n/useFormat";
import { useIngestionRuns, useTransponderAssignments } from "../connections/useConnections";
import { bestLap, DEFAULT_LAP_DISTANCE_M, flying200Ms, startOfWeek, summarizeWeek } from "./sessionStats";
import { useSessionDetail, useSessionsRange } from "./useTraining";
import "./TrackHome.css";

function delta(current: number, previous: number): { label: string; direction: DeltaDirection } | undefined {
  if (current === 0 && previous === 0) return undefined;
  const diff = current - previous;
  return { label: `${diff > 0 ? "+" : diff < 0 ? "−" : "±"}${Math.abs(diff)}`, direction: diff > 0 ? "better" : diff < 0 ? "worse" : "neutral" };
}

// How many of the newest sessions the "recent" list shows.
const RECENT_SESSIONS = 5;

/**
 * The velodrome part of Home (track athletes only): this week on the track,
 * the latest sqorz session with its best lap and flying 200, the sync status
 * and the newest sessions. Nothing until there is a session.
 */
export function TrackHome({ athleteId }: { athleteId: string }) {
  const { t } = useTranslation(["home", "training"]);
  const fmt = useFormat();
  // Only the last two weeks (the week tiles) and the newest few; not the whole history.
  const previousWeekStart = useMemo(() => {
    const start = startOfWeek(new Date());
    start.setDate(start.getDate() - 7);
    return start;
  }, []);
  const weeks = useSessionsRange(athleteId, { from: localIsoDate(previousWeekStart) });
  const sessions = useSessionsRange(athleteId, { limit: RECENT_SESSIONS });
  const runs = useIngestionRuns(athleteId);
  const assignments = useTransponderAssignments(athleteId);
  const latest = sessions.data?.[0];
  const latestDetail = useSessionDetail(athleteId, latest?.external_event_id ?? "");

  const { thisWeek, lastWeek } = useMemo(() => {
    const weekStart = startOfWeek(new Date());
    return {
      thisWeek: summarizeWeek(weeks.data ?? [], weekStart),
      lastWeek: summarizeWeek(weeks.data ?? [], previousWeekStart),
    };
  }, [weeks.data, previousWeekStart]);

  const latestBests = useMemo(() => {
    const laps = latestDetail.data?.tracks.flatMap((track) => track.laps) ?? [];
    return { lap: bestLap(laps, (lap) => lap.whole_lap_time_ms), f200: bestLap(laps, flying200Ms) };
  }, [latestDetail.data]);

  const lastRun = runs.data?.[0];
  const activeCount = assignments.data?.filter((a) => a.end_date === null).length ?? 0;

  if (!sessions.data || sessions.data.length === 0) return null;

  return (
    <section className="track-home" aria-label={t("track.title")}>
      <h2 className="track-track-home__title">{t("track.title")}</h2>
      <div className="track-home__week">
        <StatTile
          label={t("week.sessions")}
          icon={<CalendarDays aria-hidden />}
          value={thisWeek.sessions}
          delta={delta(thisWeek.sessions, lastWeek.sessions)}
          hint={t("week.vsLastWeek")}
        />
        <StatTile
          label={t("week.laps")}
          icon={<ListOrdered aria-hidden />}
          value={thisWeek.laps}
          hint={t("week.distance", { distance: fmt.distance(thisWeek.laps * DEFAULT_LAP_DISTANCE_M) })}
        />
        <StatTile
          label={t("week.trackTime")}
          icon={<Clock aria-hidden />}
          value={thisWeek.trackSeconds >= 3600 ? fmt.duration(thisWeek.trackSeconds) : Math.round(thisWeek.trackSeconds / 60)}
          unit={thisWeek.trackSeconds >= 3600 ? "h" : "min"}
        />
      </div>

      <div className="track-home__grid">
        {latest && (
          <Card
            className="track-home__latest"
            eyebrow={`${t("latest.eyebrow")} · ${fmt.date(latest.event_date, "weekday")}`}
            title={latest.event_name}
            actions={
              <ButtonLink to={`/sessions/${latest.external_event_id}`} size="sm" variant="secondary" iconRight={<ArrowRight aria-hidden />}>
                {t("latest.open")}
              </ButtonLink>
            }
          >
            <div className="track-home__latest-tracks">
              {latest.track_names.map((name) => (
                <Badge key={name}>{name}</Badge>
              ))}
            </div>
            <div className="track-home__latest-stats">
              <StatTile label={t("training:session.laps")} icon={<ListOrdered aria-hidden />} value={latest.lap_count} />
              <StatTile
                label={t("training:session.bestLap")}
                icon={<Timer aria-hidden />}
                tone="accent"
                value={latestDetail.isLoading ? "…" : fmt.lapTime(latestBests.lap?.value)}
              />
              <StatTile
                label={t("training:session.bestF200")}
                icon={<Flag aria-hidden />}
                tone="highlight"
                value={latestDetail.isLoading ? "…" : latestBests.f200 ? fmt.seconds(latestBests.f200.value) : "—"}
                unit={latestBests.f200 ? "s" : undefined}
              />
            </div>
          </Card>
        )}

        <div className="track-home__side">
          <Card title={t("sync.title")} actions={<Radio className="track-home__card-icon" aria-hidden />}>
            <div className="track-home__sync">
              {lastRun ? (
                <Badge tone={lastRun.status === "failed" ? "negative" : "positive"}>
                  {lastRun.status === "failed" ? t("sync.failed") : t("sync.lastSync", { when: fmt.relative(lastRun.requested_at) })}
                </Badge>
              ) : (
                <Badge>{t("sync.never")}</Badge>
              )}
              <p className="ui-card__hint">
                {activeCount > 0 ? t("sync.activeTransponders", { count: activeCount }) : t("sync.noActive")}
              </p>
              <Link to="/import" className="track-home__link">
                {t("sync.manage")} <ArrowRight aria-hidden />
              </Link>
            </div>
          </Card>

          <Card
            title={t("recent.title")}
            actions={
              <Link to="/log" className="track-home__link">
                {t("recent.viewAll")}
              </Link>
            }
          >
            <ul className="track-home__recent">
              {sessions.data.map((session) => (
                <li key={session.external_event_id}>
                  <Link to={`/sessions/${session.external_event_id}`} className="track-home__recent-row">
                    <span className="track-home__recent-date">{fmt.date(session.event_date, "dayMonth")}</span>
                    <span className="track-home__recent-name">{session.event_name}</span>
                    <span className="track-home__recent-laps">{t("training:log.laps", { count: session.lap_count })}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </section>
  );
}
