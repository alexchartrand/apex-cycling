import { useTranslation } from "react-i18next";
import { PageHeader } from "../components/ui";
import { FitnessCard } from "../features/activities/FitnessCard";
import { WeeklyLoadByTypeCard } from "../features/activities/WeeklyLoadByTypeCard";
import "../features/activities/Activities.css";
import { useActiveAthlete } from "../features/athletes/useActiveAthlete";
import "./ProgressPage.css";

/** Fitness: training load and form across every sport. Track lap progression lives on Records. */
export function ProgressPage() {
  const { t } = useTranslation("training");
  const athleteId = useActiveAthlete().data?.id ?? "";

  return (
    <>
      <PageHeader title={t("fitness.title")} description={t("fitness.description")} />
      {athleteId !== "" && (
        <div className="progress-page">
          <FitnessCard athleteId={athleteId} />
          <WeeklyLoadByTypeCard athleteId={athleteId} />
        </div>
      )}
    </>
  );
}
