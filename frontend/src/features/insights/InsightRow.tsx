import { CalendarCheck, Gauge, Timer, Trophy, type LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useFormat } from "../../i18n/useFormat";
import { formatRecordTime } from "../records/timeInput";
import { improvementMs } from "./insights";
import type { Insight, InsightKind } from "./types";
import "./Insights.css";

const ICONS: Record<InsightKind, LucideIcon> = {
  personal_record: Trophy,
  season_best: CalendarCheck,
  best_nth_lap: Timer,
  most_consistent: Gauge,
};

/** One headline: what happened, then the numbers behind it. */
export function InsightRow({ insight }: { insight: Insight }) {
  const { t } = useTranslation(["insights", "records"]);
  const fmt = useFormat();
  const Icon = ICONS[insight.kind];

  const event = insight.event_key ? t(`records:events.${insight.event_key as "lap"}`) : "";
  const start = (insight.start_type ?? insight.effort_start_type) ? t(`records:startTypes.${(insight.start_type ?? insight.effort_start_type)!}`) : "";
  const faster = improvementMs(insight);
  const params = {
    event,
    start,
    n: insight.lap_number ?? 0,
    count: insight.lap_count ?? 0,
    time: insight.time_ms != null ? formatRecordTime(insight.time_ms, fmt) : "",
    previous: insight.previous_ms != null ? formatRecordTime(insight.previous_ms, fmt) : "",
    faster: faster != null ? `${fmt.seconds(faster)} s` : "",
    milestone: insight.milestone_ms != null ? formatRecordTime(insight.milestone_ms, fmt) : "",
    spread: insight.cv_pct != null ? fmt.number(insight.cv_pct, 1) : "",
  };

  return (
    <div className={`insight insight--${insight.kind}`}>
      <Icon className="insight__icon" aria-hidden />
      <div className="insight__text">
        <span className="insight__title">{t(`insights:title.${insight.kind}`, params)}</span>
        <span className="insight__detail">
          {t(`insights:detail.${insight.kind}`, params)}
          {insight.milestone_ms != null && ` · ${t("insights:milestone", params)}`}
        </span>
      </div>
    </div>
  );
}
