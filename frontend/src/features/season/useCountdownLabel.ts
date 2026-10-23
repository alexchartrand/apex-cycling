import { useTranslation } from "react-i18next";
import type { Competition } from "./types";

/** "In 9 days", "Today", "3 days ago". */
export function useCountdownLabel() {
  const { t } = useTranslation("season");
  return (race: Competition) =>
    race.phase === "race_day" ? t("races.today") : race.days_until > 0 ? t("races.inDays", { count: race.days_until }) : t("races.daysAgo", { count: -race.days_until });
}
