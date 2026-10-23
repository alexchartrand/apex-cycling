import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, Tooltip, XAxis, YAxis } from "recharts";
import { useTranslation } from "react-i18next";
import { axisProps, ChartFrame, ChartTooltip, cursorProps, gridProps } from "../../../components/charts";
import { useFormat } from "../../../i18n/useFormat";
import type { Effort, Pacing } from "../types";

/** Each lap's time against the effort's even pace: bars above zero are slower laps. */
export function PacingChart({ effort, pacing }: { effort: Effort; pacing: Pacing }) {
  const { t } = useTranslation("training");
  const fmt = useFormat();
  const data = pacing.deviations_pct
    .map((pct, i) => ({ lap: i + 1, pct, skipped: pacing.start_lap_skipped && i === 0, ms: effort.lap_times_ms[i] }))
    .filter((row): row is typeof row & { pct: number } => row.pct != null);

  return (
    <ChartFrame
      height={180}
      caption={t("efforts.pacingCaption", { pace: fmt.lapTime(Math.round(pacing.even_pace_ms)) })}
      legend={[
        { label: t("efforts.paceFaster"), color: "var(--chart-1)" },
        { label: t("efforts.paceSlower"), color: "var(--chart-3)" },
      ]}
    >
      <BarChart data={data} margin={{ top: 8, right: 4, left: 0, bottom: 0 }}>
        <CartesianGrid {...gridProps} />
        <XAxis dataKey="lap" {...axisProps} interval="preserveStartEnd" minTickGap={12} />
        <YAxis tickFormatter={(pct: number) => `${fmt.number(pct, 1)} %`} width={52} {...axisProps} />
        <ReferenceLine y={0} stroke="var(--color-border-strong)" />
        <Tooltip
          cursor={{ fill: "var(--chart-grid)", fillOpacity: 0.4, ...cursorProps }}
          content={
            <ChartTooltip
              formatValue={(pct) => `${Number(pct) > 0 ? "+" : ""}${fmt.number(Number(pct), 1)} %`}
              formatLabel={(lap) => t("efforts.lapN", { n: lap })}
            />
          }
        />
        <Bar dataKey="pct" name={t("efforts.pacingTitle")} isAnimationActive={false} radius={[3, 3, 3, 3]}>
          {data.map((row) => (
            <Cell key={row.lap} fill={row.pct > 0 ? "var(--chart-3)" : "var(--chart-1)"} fillOpacity={row.skipped ? 0.4 : 1} />
          ))}
        </Bar>
      </BarChart>
    </ChartFrame>
  );
}
