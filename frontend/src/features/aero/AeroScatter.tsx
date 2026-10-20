import { useTranslation } from "react-i18next";
import { CartesianGrid, ComposedChart, Line, Scatter, Tooltip, XAxis, YAxis } from "recharts";
import { axisProps, ChartFrame, gridProps, type LegendItem } from "../../components/charts";
import { useFormat } from "../../i18n/useFormat";
import { fitLine, scatterPoints, type ScatterPoint } from "./aero";
import type { AeroConditions, AeroFit, AeroPoint } from "./types";

function PointTooltip({ active, payload }: { active?: boolean; payload?: readonly { payload?: unknown }[] }) {
  const { t } = useTranslation("aero");
  const fmt = useFormat();
  const point = payload?.[0]?.payload as ScatterPoint | undefined;
  if (!active || !point || point.lapId === undefined) return null;
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip__label">{t("chart.lap", { effort: point.effortIndex, lap: point.lapInEffort })}</div>
      <div className="chart-tooltip__row">
        <span className="chart-tooltip__value">
          {fmt.number(point.speedKmh, 1)} km/h · {fmt.number(point.powerW, 0)} W · {fmt.number(point.y, 1)} N
        </span>
      </div>
      <div className="chart-tooltip__row">
        <span className="chart-tooltip__name">{t("stats.cda")}</span>
        <span className="chart-tooltip__value">{fmt.number(point.cdaM2, 3, 3)}</span>
      </div>
    </div>
  );
}

/** Each lap's resistive force against its speed squared, with the fitted line. */
export function AeroScatter({ points, fit, conditions }: { points: AeroPoint[]; fit: AeroFit | null; conditions: AeroConditions }) {
  const { t } = useTranslation("aero");
  const fmt = useFormat();
  const rows = scatterPoints(points);
  const used = rows.filter((r) => r.used);
  const other = rows.filter((r) => !r.used);
  const line = fit ? fitLine(fit, conditions, rows.map((r) => r.x)) : [];
  const legend: LegendItem[] = [
    { label: t("chart.used"), color: "var(--chart-1)" },
    { label: t("chart.other"), color: "var(--chart-axis)" },
  ];
  if (line.length) legend.push({ label: t("chart.fit"), color: "var(--chart-3)", dashed: true });

  return (
    <ChartFrame height={300} isEmpty={rows.length === 0} emptyMessage={t("chart.empty")} legend={legend} caption={t("chart.caption")}>
      <ComposedChart margin={{ top: 8, right: 12, bottom: 18, left: 0 }}>
        <CartesianGrid {...gridProps} />
        <XAxis
          {...axisProps}
          dataKey="x"
          type="number"
          domain={["auto", "auto"]}
          tickFormatter={(v: number) => fmt.number(v, 0)}
          label={{ value: t("chart.x"), position: "insideBottom", offset: -12, fill: "var(--chart-axis)", fontSize: 12 }}
          allowDuplicatedCategory={false}
        />
        <YAxis
          {...axisProps}
          dataKey="y"
          type="number"
          width={44}
          domain={["auto", "auto"]}
          unit={` ${t("chart.y")}`}
          tickFormatter={(v: number) => fmt.number(v, 0)}
        />
        <Tooltip content={<PointTooltip />} cursor={false} />
        <Scatter name={t("chart.other")} data={other} fill="var(--chart-axis)" fillOpacity={0.6} isAnimationActive={false} />
        <Scatter name={t("chart.used")} data={used} fill="var(--chart-1)" isAnimationActive={false} />
        {line.length > 0 && (
          <Line
            data={line}
            dataKey="y"
            stroke="var(--chart-3)"
            strokeWidth={2}
            strokeDasharray="6 4"
            dot={false}
            activeDot={false}
            isAnimationActive={false}
            tooltipType="none"
          />
        )}
      </ComposedChart>
    </ChartFrame>
  );
}
