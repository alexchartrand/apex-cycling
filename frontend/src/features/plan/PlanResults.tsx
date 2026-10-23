import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Badge, type BadgeTone } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { formatRecordTime } from "../records/timeInput";
import type { StandardEventKey } from "../records/types";
import type { RepStatus } from "./types";
import { usePlanComparison } from "./usePlan";

const STATUS_TONES: Record<RepStatus, BadgeTone> = { hit: "positive", miss: "negative", ridden: "accent", not_ridden: "neutral", free: "neutral" };

/** The plan's reps against the efforts of the session ridden: hit or miss per rep. */
export function PlanResults({ athleteId, planId, eventId }: { athleteId: string; planId: string; eventId: string }) {
  const { t } = useTranslation("plan");
  const { t: tr } = useTranslation("records");
  const fmt = useFormat();
  const comparison = usePlanComparison(athleteId, planId, true);

  if (comparison.isLoading) return <p className="plan-detail__hint">{t("results.loading")}</p>;
  if (comparison.isError || !comparison.data) return <p role="alert">{t("results.error")}</p>;
  const { reps, measured, hits } = comparison.data;
  if (reps.length === 0) return null;

  return (
    <section className="plan-results" aria-label={t("results.title")}>
      <h3 className="plan-results__title">{t("results.title")}</h3>
      {measured > 0 && <p className="plan-detail__hint">{t("results.summary", { hits, measured })}</p>}
      <ul className="plan-results__list">
        {reps.map((rep) => (
          <li key={`${rep.target_index}-${rep.rep}`} className="plan-results__row">
            <span className="plan-results__what">
              {rep.label}
              {rep.event_key && ` · ${tr(`events.${rep.event_key as StandardEventKey}`)}`}
              {reps.filter((other) => other.target_index === rep.target_index).length > 1 && ` (${rep.rep})`}
            </span>
            <span className="plan-results__figures">
              {rep.time_ms != null && (
                <>
                  {rep.effort_index != null ? (
                    <Link to={`/sessions/${encodeURIComponent(eventId)}?tab=efforts`}>{formatRecordTime(rep.time_ms, fmt)}</Link>
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
    </section>
  );
}
