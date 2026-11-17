import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";
import { useTranslation } from "react-i18next";
import { axisProps, ChartFrame, ChartTooltip, cursorProps, gridProps } from "../../components/charts";
import { Card, SegmentedControl, SkeletonGroup } from "../../components/ui";
import { parseLocalDate } from "../../i18n/format";
import { useFormat } from "../../i18n/useFormat";
import { typeColor } from "./activityTypes";
import type { ActivityType } from "./types";
import { useWeeklyLoad } from "./useActivities";
import { weeklyChartRows, type WeeklyMetric } from "./weeklyLoad";

const WEEKS = 12;

/** Stacked weekly bars, one colour per kind of training (sqorz sessions are track cycling). */
export function WeeklyLoadByTypeCard({ athleteId }: { athleteId: string }) {
  const { t } = useTranslation(["activities", "common"]);
  const fmt = useFormat();
  const [metric, setMetric] = useState<WeeklyMetric>("hours");
  const weekly = useWeeklyLoad(athleteId, WEEKS);
  const { rows, types } = weeklyChartRows(weekly.data ?? [], metric);
  const formatWeek = (week: string) => fmt.date(parseLocalDate(week), "dayMonth");
  const formatValue = (value: number) => (metric === "hours" ? t("weekly.hoursValue", { value: fmt.number(value, 1) }) : fmt.number(value, 0));
  const name = (type: ActivityType) => t(`types.${type}.name`);

  return (
    <Card
      title={t("weekly.title")}
      actions={
        <SegmentedControl<WeeklyMetric>
          size="sm"
          aria-label={t("weekly.metric")}
          value={metric}
          onChange={setMetric}
          options={[
            { value: "hours", label: t("weekly.hours") },
            { value: "tss", label: t("weekly.tss") },
          ]}
        />
      }
    >
      <p className="ui-card__hint">{t("weekly.description")}</p>
      {weekly.isLoading && <SkeletonGroup lines={4} />}
      {weekly.isError && <p role="alert">{t("common:loadError")}</p>}
      {weekly.data && types.length === 0 && <p className="ui-card__hint">{t("weekly.empty")}</p>}
      {types.length > 0 && (
        <ChartFrame height={220} legend={types.map((type) => ({ label: name(type), color: typeColor(type) }))}>
          <BarChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid {...gridProps} />
            <XAxis {...axisProps} dataKey="week" tickFormatter={formatWeek} />
            <YAxis {...axisProps} width={36} tickFormatter={(v: number) => fmt.number(v, 0)} />
            <Tooltip
              cursor={cursorProps}
              content={<ChartTooltip formatLabel={(label) => t("weekly.weekOf", { date: formatWeek(String(label)) })} formatValue={formatValue} />}
            />
            {types.map((type) => (
              <Bar key={type} dataKey={type} name={name(type)} stackId="week" fill={typeColor(type)} isAnimationActive={false} />
            ))}
          </BarChart>
        </ChartFrame>
      )}
    </Card>
  );
}
