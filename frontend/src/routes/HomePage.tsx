import { CloudDownload, Radio } from "lucide-react";
import { useTranslation } from "react-i18next";
import { ButtonLink, EmptyState, SkeletonGroup } from "../components/ui";
import { FitnessCard } from "../features/activities/FitnessCard";
import { LatestActivityCard } from "../features/activities/LatestActivityCard";
import { useActivitiesRange } from "../features/activities/useActivities";
import "../features/activities/Activities.css";
import { useActiveAthlete } from "../features/athletes/useActiveAthlete";
import { FirstRunChecklist } from "../features/onboarding/FirstRunChecklist";
import { useFirstRunChecklist } from "../features/onboarding/useFirstRunChecklist";
import { WhatsNewCard } from "../features/insights/WhatsNewCard";
import { AiCoachCard } from "../features/aicoach/AiCoachCard";
import { PlannedSessionsCard } from "../features/plan/PlannedSessionsCard";
import { GoalsCard } from "../features/goals/GoalsCard";
import { NextRaceCard } from "../features/season/NextRaceCard";
import { useTransponderAssignments } from "../features/connections/useConnections";
import { cardShown } from "../features/sports/registry";
import { useMySports } from "../features/sports/useMySports";
import { TrackHome } from "../features/training/TrackHome";
import { useSessionsRange } from "../features/training/useTraining";
import { useFormat } from "../i18n/useFormat";
import "./HomePage.css";

function greetingKey(hour: number): "morning" | "afternoon" | "evening" {
  if (hour < 12) return "morning";
  if (hour < 18) return "afternoon";
  return "evening";
}

/**
 * Today first (what's planned, form, the latest activity), then what's ahead
 * (race, goals, the AI coach, new headlines) beside it, then the cards of the
 * athlete's sports (the track).
 */
export function HomePage() {
  const { t } = useTranslation(["home", "shell"]);
  const fmt = useFormat();
  const athlete = useActiveAthlete();
  const athleteId = athlete.data?.id ?? "";
  const { sports } = useMySports();
  // Same keys as the cards' own queries, so they're asked once.
  const sessions = useSessionsRange(athleteId, { limit: 5 });
  const activities = useActivitiesRange(athleteId, { limit: 1 });
  const assignments = useTransponderAssignments(athleteId);
  const firstRun = useFirstRunChecklist();

  const now = new Date();
  const firstName = athlete.data?.display_name.split(/\s+/)[0] ?? "";
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

      {athleteId !== "" && (
        <div className="home__layout">
          <div className="home__today">
            <PlannedSessionsCard athleteId={athleteId} limit={5} />
            <FitnessCard athleteId={athleteId} hideWhenEmpty compact />
            <LatestActivityCard athleteId={athleteId} />
          </div>
          <aside className="home__ahead">
            <AiCoachCard athleteId={athleteId} />
            <NextRaceCard athleteId={athleteId} />
            {!noData && <GoalsCard athleteId={athleteId} />}
            <WhatsNewCard athleteId={athleteId} />
          </aside>
        </div>
      )}

      {athleteId !== "" && cardShown("track", sports) && <TrackHome athleteId={athleteId} />}
    </div>
  );
}
