import { Flag } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Badge, Card } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { nextCompetition } from "./season";
import { useCountdownLabel } from "./useCountdownLabel";
import { useCompetitions } from "./useSeason";
import "./Season.css";

/** Home: the next race with its countdown and where the taper stands. Hidden without a race ahead. */
export function NextRaceCard({ athleteId }: { athleteId: string }) {
  const { t } = useTranslation("season");
  const fmt = useFormat();
  const competitions = useCompetitions(athleteId);
  const countdown = useCountdownLabel();
  const race = nextCompetition(competitions.data ?? []);
  if (!race) return null;
  const toTaper = race.days_to_taper;

  return (
    <Card title={t("next.title")} as="section" actions={<Link to="/season">{t("next.all")}</Link>}>
      <div className="season__next">
        <Flag aria-hidden className="season__next-icon" />
        <div className="season__next-text">
          <strong>{race.name}</strong>
          <span className="season__sub">
            {fmt.date(race.competition_date, "weekday")}
            {race.location ? ` · ${race.location}` : ""}
          </span>
        </div>
        <Badge tone={race.phase === "taper" || race.phase === "race_day" ? "highlight" : "accent"}>{countdown(race)}</Badge>
      </div>
      {race.phase === "taper" && <p className="season__sub">{t("next.taperNow")}</p>}
      {toTaper != null && <p className="season__sub">{t("races.taperIn", { count: toTaper })}</p>}
    </Card>
  );
}
