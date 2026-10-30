import { MessageSquare } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Card, PageHeader, SkeletonGroup } from "../components/ui";
import { FitnessCard } from "../features/activities/FitnessCard";
import "../features/activities/Activities.css";
import { useAthletePath, useAthleteScope } from "../features/athletes/athleteScope";
import { AthleteBadges, AthleteFacts } from "../features/coaching/AthleteSummary";
import { useCoachAthleteSummary, useCommentInbox } from "../features/coaching/useCoaching";
import { GoalsCard } from "../features/goals/GoalsCard";
import { WhatsNewCard } from "../features/insights/WhatsNewCard";
import { PlannedSessionsCard } from "../features/plan/PlannedSessionsCard";
import { NextRaceCard } from "../features/season/NextRaceCard";
import { useSessionsRange } from "../features/training/useTraining";
import { useFormat } from "../i18n/useFormat";

// How many of the newest sessions the summary lists.
const RECENT_SESSIONS = 5;

/** A coach's summary of one athlete: what needs a look, the week, form, plans, goals and the latest sessions. */
export function CoachAthletePage() {
  const { t } = useTranslation(["coach", "training"]);
  const fmt = useFormat();
  const path = useAthletePath();
  const athleteId = useAthleteScope()?.athleteId ?? "";
  const summary = useCoachAthleteSummary(athleteId);
  const sessions = useSessionsRange(athleteId, { limit: RECENT_SESSIONS });
  const threads = (useCommentInbox().data ?? []).filter((item) => item.athlete_id === athleteId);
  const card = summary.data;

  return (
    <>
      <PageHeader title={card?.athlete_name ?? " "} eyebrow={t("athlete.eyebrow")} description={t("athlete.readOnly")} />
      {summary.isLoading && <SkeletonGroup lines={6} />}
      {card && (
        <div className="coach-athlete">
          <AthleteBadges card={card} />
          <div className="coach-athlete__grid">
            <Card title={t("athlete.overview")} as="section">
              <AthleteFacts card={card} />
            </Card>

            <PlannedSessionsCard athleteId={athleteId} alwaysShow />

            {threads.length > 0 && (
              <Card title={t("athlete.threads")} as="section" actions={<MessageSquare className="coach-athlete__icon" aria-hidden />}>
                <ul className="coach-athlete__list">
                  {threads.map((item) => (
                    <li key={item.external_event_id}>
                      <Link to={path(`/sessions/${encodeURIComponent(item.external_event_id)}?tab=comments`)} className="coach-athlete__row">
                        <span className="coach-athlete__main">
                          <span>{item.event_name}</span>
                          <span className="coach-athlete__sub">{item.latest_excerpt}</span>
                        </span>
                        <span className="coach-athlete__sub">{t("waiting.newComments", { count: item.unread_count })}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </Card>
            )}

            <Card
              title={t("athlete.recent")}
              as="section"
              actions={<Link to={path("/log")}>{t("athlete.allSessions")}</Link>}
            >
              {sessions.isLoading && <SkeletonGroup lines={3} />}
              {sessions.data?.length === 0 && <p className="coach-muted">{t("cards.noSessions")}</p>}
              <ul className="coach-athlete__list">
                {sessions.data?.map((session) => (
                  <li key={session.external_event_id}>
                    <Link to={path(`/sessions/${encodeURIComponent(session.external_event_id)}`)} className="coach-athlete__row">
                      <span className="coach-athlete__date">{fmt.date(session.event_date, "dayMonth")}</span>
                      <span className="coach-athlete__main">{session.event_name}</span>
                      <span className="coach-athlete__sub">{t("training:log.laps", { count: session.lap_count })}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </Card>

            <NextRaceCard athleteId={athleteId} />
            <WhatsNewCard athleteId={athleteId} />
          </div>
          <FitnessCard athleteId={athleteId} hideWhenEmpty />
          <GoalsCard athleteId={athleteId} />
        </div>
      )}
    </>
  );
}
