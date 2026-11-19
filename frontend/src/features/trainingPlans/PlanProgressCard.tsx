import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";
import { useTranslation } from "react-i18next";
import { axisProps, ChartFrame, ChartTooltip, cursorProps, gridProps } from "../../components/charts";
import { Card, ProgressBar, StatTile } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import type { PlanProgress } from "./types";

const PLANNED_COLOR = "var(--chart-grid)";
const DONE_COLOR = "var(--chart-1)";

/** Done / missed / to come, and the planned against the done hours of each week. */
export function PlanProgressCard({ progress }: { progress: PlanProgress }) {
  const { t } = useTranslation("trainingPlans");
  const fmt = useFormat();
  const rows = progress.weeks.map((week) => ({
    week: week.week_start,
    planned: Math.round((week.planned_s / 3600) * 10) / 10,
    done: Math.round((week.done_s / 3600) * 10) / 10,
  }));
  const formatWeek = (week: string) => fmt.date(week, "dayMonth");
  const nothing = progress.weeks.length === 0;

  return (
    <Card as="section" title={t("progress.title")}>
      {nothing ? (
        <p className="ui-card__hint">{t("progress.noSessions")}</p>
      ) : (
        <>
          <div className="tplan-stats">
            <StatTile label={t("progress.done")} value={progress.done} tone="accent" />
            <StatTile label={t("progress.missed")} value={progress.missed} tone={progress.missed > 0 ? "marker" : "default"} />
            <StatTile label={t("progress.skipped")} value={progress.skipped} />
            <StatTile label={t("progress.upcoming")} value={progress.upcoming} />
          </div>
          {progress.compliance != null && (
            <div className="tplan-compliance">
              <span>
                {t("progress.compliance")} · {fmt.number(progress.compliance * 100, 0)} %
              </span>
              <ProgressBar value={progress.compliance} label={t("progress.compliance")} tone="positive" />
            </div>
          )}
          <ChartFrame
            height={200}
            legend={[
              { label: t("progress.planned"), color: PLANNED_COLOR },
              { label: t("progress.ridden"), color: DONE_COLOR },
            ]}
          >
            <BarChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }} barGap={0}>
              <CartesianGrid {...gridProps} />
              <XAxis {...axisProps} dataKey="week" tickFormatter={formatWeek} />
              <YAxis {...axisProps} width={32} allowDecimals={false} tickFormatter={(v: number) => fmt.number(v, 0)} />
              <Tooltip
                cursor={cursorProps}
                content={
                  <ChartTooltip
                    formatLabel={(label) => t("outline.weekOf", { date: formatWeek(String(label)) })}
                    formatValue={(value: number) => t("hoursPerWeek", { value: fmt.number(value, 1) })}
                  />
                }
              />
              <Bar dataKey="planned" name={t("progress.planned")} fill={PLANNED_COLOR} isAnimationActive={false} />
              <Bar dataKey="done" name={t("progress.ridden")} fill={DONE_COLOR} isAnimationActive={false} />
            </BarChart>
          </ChartFrame>
          <p className="ui-card__hint">{t("progress.weekly")}</p>
        </>
      )}
    </Card>
  );
}
