import { CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from "recharts";
import { axisProps, ChartFrame, ChartTooltip, cursorProps, gridProps, type LegendItem } from "../../components/charts";
import { useFormat } from "../../i18n/useFormat";
import { durationLabel, CURVE_TICKS_S } from "./format";
import type { CurveRow } from "./powerCurve";

/** Best power per duration on a log duration axis; a second series is optional. */
export function CurveChart({
  rows,
  unit,
  seriesA,
  seriesB,
  height = 280,
  emptyMessage,
  perKg = false,
}: {
  rows: CurveRow[];
  unit: string;
  seriesA: string;
  seriesB?: string;
  height?: number;
  emptyMessage: string;
  perKg?: boolean;
}) {
  const fmt = useFormat();
  const max = rows.length > 0 ? rows[rows.length - 1].duration_s : 1;
  const ticks = CURVE_TICKS_S.filter((tick) => tick <= max);
  const legend: LegendItem[] = [{ label: seriesA, color: "var(--chart-1)" }];
  if (seriesB) legend.push({ label: seriesB, color: "var(--chart-3)", dashed: true });
  const digits = perKg ? 2 : 0;

  return (
    <ChartFrame height={height} isEmpty={rows.length === 0} emptyMessage={emptyMessage} legend={seriesB ? legend : undefined}>
      <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
        <CartesianGrid {...gridProps} />
        <XAxis
          {...axisProps}
          dataKey="duration_s"
          type="number"
          scale="log"
          domain={[1, max]}
          ticks={ticks}
          tickFormatter={durationLabel}
          allowDataOverflow
        />
        <YAxis {...axisProps} width={44} unit="" tickFormatter={(v: number) => fmt.number(v, digits)} domain={[0, "auto"]} />
        <Tooltip
          cursor={cursorProps}
          content={
            <ChartTooltip
              formatLabel={(label) => durationLabel(Number(label))}
              formatValue={(value) => `${fmt.number(value, digits)} ${unit}`}
            />
          }
        />
        <Line type="monotone" dataKey="a" name={seriesA} stroke="var(--chart-1)" strokeWidth={2.5} dot={false} isAnimationActive={false} connectNulls />
        {seriesB && (
          <Line type="monotone" dataKey="b" name={seriesB} stroke="var(--chart-3)" strokeWidth={2} strokeDasharray="6 4" dot={false} isAnimationActive={false} connectNulls />
        )}
      </LineChart>
    </ChartFrame>
  );
}
