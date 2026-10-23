import { useTranslation } from "react-i18next";
import { PageHeader } from "../components/ui";
import { useActiveAthlete } from "../features/athletes/useActiveAthlete";
import { CalendarFeedCard } from "../features/season/CalendarFeedCard";
import { CompetitionsCard } from "../features/season/CompetitionsCard";
import { SeasonsCard } from "../features/season/SeasonsCard";
import "../features/season/Season.css";

/** The race calendar with its taper countdown, the seasons with their bests, and the phone-calendar link. */
export function SeasonPage() {
  const { t } = useTranslation("season");
  const athleteId = useActiveAthlete().data?.id ?? "";

  return (
    <>
      <PageHeader title={t("title")} description={t("description")} />
      {athleteId !== "" && (
        <div className="season__page">
          <CompetitionsCard athleteId={athleteId} />
          <SeasonsCard athleteId={athleteId} />
          <CalendarFeedCard athleteId={athleteId} />
        </div>
      )}
    </>
  );
}
