import { useTranslation } from "react-i18next";
import { localIsoDate } from "../../i18n/format";
import { useFormat } from "../../i18n/useFormat";
import { phaseColor, timeline } from "./phases";
import type { TrainingPlan } from "./types";

/**
 * The plan's phases as coloured blocks over its weeks, with today and the race
 * marked. `compact` is the thin bar of the plan list (no ticks, no labels).
 */
export function PhaseTimeline({ plan, compact = false }: { plan: TrainingPlan; compact?: boolean }) {
  const { t } = useTranslation("trainingPlans");
  const fmt = useFormat();
  const layout = timeline(plan.start_date, plan.end_date, plan.phases, localIsoDate(new Date()), plan.race?.date ?? plan.goal_date);
  const label = plan.phases
    .map((phase) => `${phase.name || t(`phase.kinds.${phase.kind}`)}: ${fmt.date(phase.start, "dayMonth")} – ${fmt.date(phase.end, "dayMonth")}`)
    .join("; ");

  return (
    <div className={compact ? "phase-timeline phase-timeline--compact" : "phase-timeline"}>
      <div className="phase-timeline__track" role="img" aria-label={`${t("phase.timeline")}. ${label || t("phase.none")}`}>
        {layout.blocks.map((block) => (
          <div
            key={block.index}
            className={block.index === plan.current_phase ? "phase-timeline__block phase-timeline__block--current" : "phase-timeline__block"}
            style={{ left: `${block.left}%`, width: `${block.width}%`, background: phaseColor(block.phase.kind) }}
            title={`${block.phase.name || t(`phase.kinds.${block.phase.kind}`)} · ${fmt.date(block.phase.start, "dayMonth")} – ${fmt.date(block.phase.end, "dayMonth")}`}
          >
            {!compact && block.width > 9 && <span className="phase-timeline__name">{block.phase.name || t(`phase.kinds.${block.phase.kind}`)}</span>}
          </div>
        ))}
        {!compact &&
          layout.weeks.map((week) => <span key={week.day} className="phase-timeline__tick" style={{ left: `${week.left}%` }} aria-hidden />)}
        {layout.race != null && <span className="phase-timeline__race" style={{ left: `${layout.race}%` }} title={t("phase.raceDay")} aria-hidden />}
        {layout.today != null && <span className="phase-timeline__today" style={{ left: `${layout.today}%` }} title={t("phase.today")} aria-hidden />}
      </div>
      {!compact && (
        <div className="phase-timeline__ends" aria-hidden>
          <span>{fmt.date(plan.start_date, "dayMonth")}</span>
          <span>{fmt.date(plan.end_date, "dayMonth")}</span>
        </div>
      )}
    </div>
  );
}
