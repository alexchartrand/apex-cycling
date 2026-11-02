import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Badge, type BadgeTone } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { formatRecordTime } from "../records/timeInput";
import type { StandardEventKey } from "../records/types";
import { clockText } from "../workouts/profile";
import type { RepStatus, StepResult, StepStatus } from "./types";
import { usePlanComparison } from "./usePlan";
import { useAthletePath } from "../athletes/athleteScope";

const STATUS_TONES: Record<RepStatus, BadgeTone> = { hit: "positive", miss: "negative", ridden: "accent", not_ridden: "neutral", free: "neutral" };
const STEP_TONES: Record<StepStatus, BadgeTone> = { hit: "positive", under: "negative", over: "marker", not_ridden: "neutral", unmeasured: "neutral" };

/** The plan against what was ridden: hit or miss per rep against the session's efforts, and on target
 * or not per power/cadence step against the recording. */
export function PlanResults({ athleteId, planId, eventId }: { athleteId: string; planId: string; eventId: string | null }) {
  const path = useAthletePath();
  const { t } = useTranslation("plan");
  const { t: tr } = useTranslation("records");
  const fmt = useFormat();
  const comparison = usePlanComparison(athleteId, planId, true);

  if (comparison.isLoading) return <p className="plan-detail__hint">{t("results.loading")}</p>;
  if (comparison.isError || !comparison.data) return <p role="alert">{t("results.error")}</p>;
  const { reps, measured, hits, recording, steps, power_measured, power_hits } = comparison.data;
  if (reps.length === 0 && steps.length === 0) {
    return recording ? null : <p className="plan-detail__hint">{t("results.noRecording")}</p>;
  }

  return (
    <section className="plan-results" aria-label={t("results.title")}>
      <h3 className="plan-results__title">{t("results.title")}</h3>
      {reps.length > 0 && (
        <>
          {measured > 0 && <p className="plan-detail__hint">{t("results.summary", { hits, measured })}</p>}
          <ul className="plan-results__list" aria-label={t("results.efforts")}>
            {reps.map((rep) => (
              <li key={`${rep.target_index}-${rep.rep}`} className="plan-results__row">
                <span className="plan-results__what">
                  {[rep.label, rep.event_key ? tr(`events.${rep.event_key as StandardEventKey}`) : null].filter(Boolean).join(" · ")}
                  {reps.filter((other) => other.target_index === rep.target_index).length > 1 && ` (${rep.rep})`}
                </span>
                <span className="plan-results__figures">
                  {rep.time_ms != null && (
                    <>
                      {rep.effort_index != null && eventId ? (
                        <Link to={path(`/sessions/${encodeURIComponent(eventId)}?tab=efforts`)}>{formatRecordTime(rep.time_ms, fmt)}</Link>
                      ) : (
                        formatRecordTime(rep.time_ms, fmt)
                      )}
                      {rep.delta_ms != null && ` (${fmt.deltaSeconds(rep.delta_ms, 2)} s)`}
                    </>
                  )}
                  {rep.target_time_ms != null && rep.time_ms != null && <span className="plan-results__target"> / {formatRecordTime(rep.target_time_ms, fmt)}</span>}
                </span>
                <Badge tone={STATUS_TONES[rep.status]}>{t(`results.status.${rep.status}`)}</Badge>
              </li>
            ))}
          </ul>
        </>
      )}
      {steps.length > 0 && (
        <>
          {recording && (
            <p className="plan-detail__hint">
              {t("results.readFrom")} <Link to={path(`/activities/${recording.id}`)}>{recording.name ?? t("detail.ride")}</Link>
              {power_measured > 0 && ` · ${t("results.powerSummary", { hits: power_hits, measured: power_measured })}`}
            </p>
          )}
          <ul className="plan-results__list" aria-label={t("results.steps")}>
            {steps.map((step) => (
              <StepRow key={step.step_index} step={step} />
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

function StepRow({ step }: { step: StepResult }) {
  const { t } = useTranslation("plan");
  const { t: tw } = useTranslation("workouts");
  const fmt = useFormat();
  const range = (low: number, high: number | null) =>
    high != null && Math.round(high) !== Math.round(low) ? `${fmt.number(low, 0)}–${fmt.number(high, 0)}` : fmt.number(low, 0);

  const powerTarget =
    step.power_low_w != null
      ? `${range(step.power_low_w, step.power?.high != null ? step.power_high_w : null)} ${tw("units.w")}`
      : step.power
        ? `${range(step.power.low, step.power.high)} ${step.power.unit === "ftp_pct" ? tw("units.ftpPct") : tw("units.w")}`
        : null;
  const figures = [
    powerTarget && `${step.avg_power_w != null ? `${fmt.number(step.avg_power_w, 0)} ${tw("units.w")}` : "–"} / ${powerTarget}`,
    step.cadence &&
      `${step.avg_cadence != null ? `${fmt.number(step.avg_cadence, 0)} ${tw("units.rpm")}` : "–"} / ${range(step.cadence.low, step.cadence.high)} ${tw("units.rpm")}`,
  ].filter(Boolean);

  return (
    <li className="plan-results__row">
      <span className="plan-results__what">
        {step.label ?? tw(`kinds.${step.kind}`)}
        {step.start_s != null && <span className="plan-results__target"> · {clockText(step.start_s)}</span>}
      </span>
      <span className="plan-results__figures">{figures.join(" · ")}</span>
      <span className="plan-results__badges">
        {step.power_status && <Badge tone={STEP_TONES[step.power_status]}>{t(`results.stepStatus.${step.power_status}`)}</Badge>}
        {step.cadence_status && (
          <Badge tone={STEP_TONES[step.cadence_status]}>{t("results.cadence", { status: t(`results.stepStatus.${step.cadence_status}`) })}</Badge>
        )}
      </span>
    </li>
  );
}
