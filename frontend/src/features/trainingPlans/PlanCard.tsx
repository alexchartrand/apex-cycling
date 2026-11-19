import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Badge } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { TypeBadge } from "../activities/TypeBadge";
import { useAthletePath } from "../athletes/athleteScope";
import { useAuthorText } from "./useAuthorText";
import { PhaseTimeline } from "./PhaseTimeline";
import type { TrainingPlan } from "./types";

/** One plan in the list: sport, goal, dates, its phases at a glance and how far it has got. */
export function PlanCard({ plan }: { plan: TrainingPlan }) {
  const { t } = useTranslation("trainingPlans");
  const fmt = useFormat();
  const path = useAthletePath();
  const authorText = useAuthorText();
  const current = plan.current_phase != null ? plan.phases[plan.current_phase] : null;
  const { done, upcoming, missed } = plan.progress;

  return (
    <Link to={path(`/plans/${plan.id}`)} className="tplan-card">
      <div className="tplan-card__head">
        <span className="tplan-card__name">{plan.name}</span>
        <TypeBadge type={plan.sport} short />
      </div>
      {plan.goal_text && (
        <p className="tplan-card__goal">
          {plan.goal_text}
          {plan.goal_date && <span className="tplan-muted"> · {t("goalBy", { date: fmt.date(plan.goal_date, "medium") })}</span>}
        </p>
      )}
      <PhaseTimeline plan={plan} compact />
      <div className="tplan-card__meta">
        <span>{t("range", { start: fmt.date(plan.start_date, "dayMonth"), end: fmt.date(plan.end_date, "medium") })}</span>
        {plan.state === "upcoming" ? (
          <Badge>{t("state.upcoming", { date: fmt.date(plan.start_date, "dayMonth") })}</Badge>
        ) : plan.state === "finished" ? (
          <Badge>{t("state.finished")}</Badge>
        ) : (
          current && <Badge tone="accent">{t("phase.current", { phase: current.name || t(`phase.kinds.${current.kind}`) })}</Badge>
        )}
        <span className="tplan-muted">{authorText(plan)}</span>
      </div>
      {done + upcoming + missed > 0 && (
        <div className="tplan-card__counts tplan-muted">
          {t("progress.done")} {done} · {t("progress.missed")} {missed} · {t("progress.upcoming")} {upcoming}
        </div>
      )}
    </Link>
  );
}
