import { useMemo } from "react";
import { ArrowRight, CalendarDays, Clock, CloudDownload, Flag, ListOrdered, Radio, Timer } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Badge, ButtonLink, Card, EmptyState, SkeletonGroup, StatTile, type DeltaDirection } from "../components/ui";
import { FitnessCard } from "../features/activities/FitnessCard";
import { useActivities } from "../features/activities/useActivities";
import "../features/activities/Activities.css";
import { useActiveAthlete } from "../features/athletes/useActiveAthlete";
import { FirstRunChecklist } from "../features/onboarding/FirstRunChecklist";
import { useFirstRunChecklist } from "../features/onboarding/useFirstRunChecklist";
import { WhatsNewCard } from "../features/insights/WhatsNewCard";
import { PlannedSessionsCard } from "../features/plan/PlannedSessionsCard";
import { GoalsCard } from "../features/goals/GoalsCard";
import { useIngestionRuns, useTransponderAssignments } from "../features/connections/useConnections";
import { bestLap, DEFAULT_LAP_DISTANCE_M, flying200Ms, startOfWeek, summarizeWeek } from "../features/training/sessionStats";
import { useSessionDetail, useSessions } from "../features/training/useTraining";
import { useFormat } from "../i18n/useFormat";
import "./HomePage.css";

function greetingKey(hour: number): "morning" | "afternoon" | "evening" {
  if (hour < 12) return "morning";
  if (hour < 18) return "afternoon";
  return "evening";
}

function delta(current: number, previous: number): { label: string; direction: DeltaDirection } | undefined {
  if (current === 0 && previous === 0) return undefined;
  const diff = current - previous;
  return { label: `${diff > 0 ? "+" : diff < 0 ? "−" : "±"}${Math.abs(diff)}`, direction: diff > 0 ? "better" : diff < 0 ? "worse" : "neutral" };
}

export function HomePage() {
  const { t } = useTranslation(["home", "training", "shell"]);
  const fmt = useFormat();
  const athlete = useActiveAthlete();
  const athleteId = athlete.data?.id ?? "";
  const sessions = useSessions(athleteId);
  const activities = useActivities(athleteId);
  const runs = useIngestionRuns(athleteId);
  const assignments = useTransponderAssignments(athleteId);
  const latest = sessions.data?.[0];
  const firstRun = useFirstRunChecklist();
  const latestDetail = useSessionDetail(athleteId, latest?.external_event_id ?? "");

  const now = new Date();
  const firstName = athlete.data?.display_name.split(/\s+/)[0] ?? "";

  const { thisWeek, lastWeek } = useMemo(() => {
    const weekStart = startOfWeek(new Date());
    const previousStart = new Date(weekStart);
    previousStart.setDate(previousStart.getDate() - 7);
    return {
      thisWeek: summarizeWeek(sessions.data ?? [], weekStart),
      lastWeek: summarizeWeek(sessions.data ?? [], previousStart),
    };
  }, [sessions.data]);

  const latestBests = useMemo(() => {
    const laps = latestDetail.data?.tracks.flatMap((track) => track.laps) ?? [];
    return { lap: bestLap(laps, (lap) => lap.whole_lap_time_ms), f200: bestLap(laps, flying200Ms) };
  }, [latestDetail.data]);

  const lastRun = runs.data?.[0];
  const activeCount = assignments.data?.filter((a) => a.end_date === null).length ?? 0;
  const noData = sessions.data?.length === 0 && assignments.data?.length === 0 && activities.data?.length === 0;

  return (
    <div className="home">
      <header className="home__hero">
        <div>
          <span className="eyebrow">{fmt.date(now, "long")}</span>
          <h1 className="home__greeting">{t(`greeting.${greetingKey(now.getHours())}`, { name: firstName })}</h1>
        </div>
        <ButtonLink to="/import" size="sm" variant="secondary" icon={<CloudDownload aria-hidden />}>
          {t("shell:nav.import")}
        </ButtonLink>
      </header>

      {(athlete.isLoading || sessions.isLoading) && <SkeletonGroup lines={6} />}

      {firstRun.visible && firstRun.checklist && <FirstRunChecklist checklist={firstRun.checklist} onHide={firstRun.hide} />}

      {noData && !firstRun.visible && (
        <EmptyState
          icon={<Radio aria-hidden />}
          title={t("onboarding.title")}
          description={t("onboarding.description")}
          action={<ButtonLink to="/import">{t("onboarding.action")}</ButtonLink>}
        />
      )}

      {athleteId !== "" && <WhatsNewCard athleteId={athleteId} />}

      {athleteId !== "" && <FitnessCard athleteId={athleteId} hideWhenEmpty />}

      {athleteId !== "" && <PlannedSessionsCard athleteId={athleteId} />}

      {athleteId !== "" && !noData && <GoalsCard athleteId={athleteId} />}

      {sessions.data && sessions.data.length > 0 && (
        <>
          <div className="home__week">
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

          <div className="home__grid">
            {latest && (
              <Card
                className="home__latest"
                eyebrow={`${t("latest.eyebrow")} · ${fmt.date(latest.event_date, "weekday")}`}
                title={latest.event_name}
                actions={
                  <ButtonLink to={`/sessions/${latest.external_event_id}`} size="sm" variant="secondary" iconRight={<ArrowRight aria-hidden />}>
                    {t("latest.open")}
                  </ButtonLink>
                }
              >
                <div className="home__latest-tracks">
                  {latest.track_names.map((name) => (
                    <Badge key={name}>{name}</Badge>
                  ))}
                </div>
                <div className="home__latest-stats">
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

            <div className="home__side">
              <Card title={t("sync.title")} actions={<Radio className="home__card-icon" aria-hidden />}>
                <div className="home__sync">
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
                  <Link to="/import" className="home__link">
                    {t("sync.manage")} <ArrowRight aria-hidden />
                  </Link>
                </div>
              </Card>

              <Card
                title={t("recent.title")}
                actions={
                  <Link to="/log" className="home__link">
                    {t("recent.viewAll")}
                  </Link>
                }
              >
                <ul className="home__recent">
                  {sessions.data.slice(0, 5).map((session) => (
                    <li key={session.external_event_id}>
                      <Link to={`/sessions/${session.external_event_id}`} className="home__recent-row">
                        <span className="home__recent-date">{fmt.date(session.event_date, "dayMonth")}</span>
                        <span className="home__recent-name">{session.event_name}</span>
                        <span className="home__recent-laps">{t("training:log.laps", { count: session.lap_count })}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
