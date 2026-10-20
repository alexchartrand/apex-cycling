import { Bar, BarChart, CartesianGrid, Cell, Tooltip, XAxis, YAxis } from "recharts";
import { useTranslation } from "react-i18next";
import { axisProps, ChartFrame, ChartTooltip, cursorProps, gridProps, secondsDomain } from "../../../components/charts";
import { useFormat } from "../../../i18n/useFormat";
import type { HalfLapSplit } from "../types";

// P2→P1 and P1→P2 are the two halves of a lap, so they get their own colour:
// a pacing drift shows as the two series separating.
const DIRECTION_COLORS = ["var(--chart-1)", "var(--chart-3)"] as const;

/** Bars of the time between consecutive pursuit lines, in ride order. */
export function HalfLapSplitChart({ splits }: { splits: HalfLapSplit[] }) {
  const { t } = useTranslation("training");
  const fmt = useFormat();

  const directions = [...new Set(splits.map((s) => `${s.from_line}→${s.to_line}`))];
  const data = splits
    .filter((s) => s.time_ms != null)
    .map((s) => ({
      n: s.index + 1,
      ms: s.time_ms as number,
      direction: `${s.from_line}→${s.to_line}`,
      color: DIRECTION_COLORS[directions.indexOf(`${s.from_line}→${s.to_line}`) % DIRECTION_COLORS.length],
    }));

  return (
    <ChartFrame
      height={200}
      isEmpty={data.length === 0}
      emptyMessage={t("efforts.noSplits")}
      caption={t("efforts.splitsCaption")}
      legend={directions.map((direction, i) => ({
        label: t("efforts.split", { from: direction.split("→")[0], to: direction.split("→")[1] }),
        color: DIRECTION_COLORS[i % DIRECTION_COLORS.length],
      }))}
    >
      <BarChart data={data} margin={{ top: 8, right: 4, left: 0, bottom: 0 }}>
        <CartesianGrid {...gridProps} />
        <XAxis dataKey="n" {...axisProps} interval="preserveStartEnd" minTickGap={12} />
        <YAxis domain={secondsDomain} tickFormatter={(ms: number) => fmt.seconds(ms, 1)} width={44} {...axisProps} />
        <Tooltip
          cursor={{ fill: "var(--chart-grid)", fillOpacity: 0.4, ...cursorProps }}
          content={
            <ChartTooltip
              formatValue={(ms) => `${fmt.seconds(ms)} s`}
              formatLabel={(n) => {
                const [from, to] = (data.find((d) => d.n === Number(n))?.direction ?? "→").split("→");
                return t("efforts.split", { from, to });
              }}
            />
          }
        />
        <Bar dataKey="ms" name={t("efforts.splitsTitle")} isAnimationActive={false} radius={[3, 3, 0, 0]}>
          {data.map((d) => (
            <Cell key={d.n} fill={d.color} />
          ))}
        </Bar>
      </BarChart>
    </ChartFrame>
  );
}
