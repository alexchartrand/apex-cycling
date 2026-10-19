import { CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from "recharts";
import { useTranslation } from "react-i18next";
import { axisProps, ChartFrame, ChartTooltip, cursorProps, gridProps, secondsDomain } from "../../components/charts";
import { useFormat } from "../../i18n/useFormat";
import { flying200Ms, lapNumber } from "./sessionStats";
import type { LapDetail } from "./types";

export type LapChartMetric = "lapTime" | "flying200" | "none";

const METRIC_SERIES: Record<Exclude<LapChartMetric, "none">, { dataKey: "lapTimeMs" | "flying200Ms"; color: string }> = {
  lapTime: { dataKey: "lapTimeMs", color: "var(--chart-1)" },
  flying200: { dataKey: "flying200Ms", color: "var(--chart-3)" },
};

function HighlightDot({
  cx,
  cy,
  lapId,
  selectedLapId,
  color,
}: {
  cx?: number;
  cy?: number;
  lapId?: string;
  selectedLapId: string | null;
  color: string;
}) {
  if (cx == null || cy == null) return null;
  const selected = lapId != null && lapId === selectedLapId;
  return (
    <circle
      cx={cx}
      cy={cy}
      r={selected ? 6 : 2.5}
      fill={color}
      stroke={selected ? "var(--color-text)" : "none"}
      strokeWidth={selected ? 2 : 0}
    />
  );
}

/** Lap-by-lap chart with an independently chosen metric per Y axis. */
export function LapChart({
  laps,
  selectedLapId,
  leftMetric,
  rightMetric,
}: {
  laps: LapDetail[];
  selectedLapId: string | null;
  leftMetric: LapChartMetric;
  rightMetric: LapChartMetric;
}) {
  const { t } = useTranslation("training");
  const fmt = useFormat();
  const rows = laps.map((lap, index) => ({
    lapId: lap.lap_id,
    label: String(lapNumber(lap, index)),
    lapTimeMs: lap.whole_lap_time_ms,
    flying200Ms: flying200Ms(lap),
  }));
  const chosen = [
    { id: "left" as const, metric: leftMetric },
    { id: "right" as const, metric: rightMetric },
  ].filter((a): a is { id: "left" | "right"; metric: Exclude<LapChartMetric, "none"> } => a.metric !== "none");
  // An axis whose metric has no values in this session (e.g. no flying-200
  // view on a gate track) would only add an empty scale and legend entry.
  const axes = chosen.filter((axis) => rows.some((row) => row[METRIC_SERIES[axis.metric].dataKey] != null));

  const data = rows.filter((row) => axes.some((axis) => row[METRIC_SERIES[axis.metric].dataKey] != null));

  const emptyMessage = chosen.length === 0 ? t("session.chartNoMetric") : t("session.chartNoData");

  return (
    <ChartFrame
      height={240}
      isEmpty={axes.length === 0 || data.length === 0}
      emptyMessage={emptyMessage}
      caption={t("session.chartCaption")}
      legend={axes.map((axis) => ({
        label: t(`session.metrics.${axis.metric}`),
        color: METRIC_SERIES[axis.metric].color,
      }))}
    >
      <LineChart data={data} margin={{ top: 8, right: 4, left: 0, bottom: 0 }}>
        <CartesianGrid {...gridProps} />
        <XAxis dataKey="label" {...axisProps} interval="preserveStartEnd" minTickGap={16} />
        {axes.map((axis) => (
          <YAxis
            key={axis.id}
            yAxisId={axis.id}
            orientation={axis.id}
            domain={secondsDomain}
            tickFormatter={(ms: number) => fmt.seconds(ms, 1)}
            width={44}
            {...axisProps}
          />
        ))}
        <Tooltip
          cursor={cursorProps}
          content={
            <ChartTooltip
              formatValue={(ms) => `${fmt.seconds(ms)} s`}
              formatLabel={(label) => t("session.lapNumber", { n: label })}
            />
          }
        />
        {axes.map((axis) => {
          const series = METRIC_SERIES[axis.metric];
          return (
            <Line
              key={axis.id}
              yAxisId={axis.id}
              type="monotone"
              dataKey={series.dataKey}
              name={t(`session.metrics.${axis.metric}`)}
              stroke={series.color}
              strokeWidth={2}
              connectNulls
              isAnimationActive={false}
              dot={(props: { cx?: number; cy?: number; index?: number; payload?: { lapId: string } }) => (
                <HighlightDot
                  key={props.payload?.lapId ?? props.index}
                  cx={props.cx}
                  cy={props.cy}
                  lapId={props.payload?.lapId}
                  selectedLapId={selectedLapId}
                  color={series.color}
                />
              )}
            />
          );
        })}
      </LineChart>
    </ChartFrame>
  );
}
