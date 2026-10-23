import { Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceLine, Tooltip, XAxis, YAxis } from "recharts";
import { useTranslation } from "react-i18next";
import { axisProps, ChartFrame, ChartTooltip, cursorProps, gridProps, secondsDomain } from "../../components/charts";
import { Card } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import type { Effort } from "../training/types";
import { better, cumulativeDelta, lapRows, splitRows, type Side } from "./compare";

const A_COLOR = "var(--chart-1)";
const B_COLOR = "var(--chart-3)";

type Row = {
  id: string;
  a: number | null | undefined;
  b: number | null | undefined;
  format: (value: number) => string;
  /** Left out when neither side has it; no winner when absent. */
  direction?: "lower" | "higher";
  /** Show B − A in this unit. */
  delta?: (diff: number) => string;
};

/** Two efforts side by side: a figures table, the lap overlay, the running gap and the half-lap splits. */
export function CompareView({ a, b, nameA, nameB }: { a: Effort; b: Effort; nameA: string; nameB: string }) {
  const { t } = useTranslation("compare");
  const { t: tt } = useTranslation("training");
  const { t: tr } = useTranslation("records");
  const fmt = useFormat();

  const candidates: Row[] = [
    { id: "laps", a: a.completed_lap_count, b: b.completed_lap_count, format: (v) => String(v) },
    { id: "total", a: a.total_time_ms, b: b.total_time_ms, format: fmt.lapTime, direction: "lower", delta: (d) => `${fmt.deltaSeconds(d)} s` },
    { id: "bestLap", a: a.best_lap_ms, b: b.best_lap_ms, format: fmt.lapTime, direction: "lower", delta: (d) => `${fmt.deltaSeconds(d)} s` },
    { id: "avgSpeed", a: a.avg_speed_kmh, b: b.avg_speed_kmh, format: (v) => `${fmt.number(v, 1, 1)} km/h`, direction: "higher" },
    { id: "topSpeed", a: a.peak_speed_kmh, b: b.peak_speed_kmh, format: (v) => `${fmt.number(v, 1, 1)} km/h`, direction: "higher" },
    { id: "spread", a: a.pacing?.cv_pct, b: b.pacing?.cv_pct, format: (v) => `${fmt.number(v, 1, 1)} %`, direction: "lower" },
    { id: "fade", a: a.pacing?.fade_pct, b: b.pacing?.fade_pct, format: (v) => `${v > 0 ? "+" : ""}${fmt.number(v, 1, 1)} %`, direction: "lower" },
    { id: "power", a: a.avg_power_w, b: b.avg_power_w, format: (v) => `${fmt.number(v, 0)} W` },
    { id: "heartRate", a: a.avg_heart_rate, b: b.avg_heart_rate, format: (v) => `${fmt.number(v, 0)} bpm` },
  ];
  const rows = candidates.filter((row) => row.a != null || row.b != null);

  const laps = lapRows(a, b).map((row) => ({ lap: row.lap, a: row.a, b: row.b }));
  const gap = cumulativeDelta(a, b);
  const splits = splitRows(a, b);
  const winnerClass = (side: Side, winner: Side | null) => (winner === side ? "compare-table__best" : undefined);

  return (
    <div className="compare-view">
      <Card title={t("figures")}>
        <table className="compare-table">
          <thead>
            <tr>
              <th scope="col">
                <span className="visually-hidden">{t("figure")}</span>
              </th>
              <th scope="col" className="compare-table__a">
                {nameA}
              </th>
              <th scope="col" className="compare-table__b">
                {nameB}
              </th>
              <th scope="col">{t("difference")}</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row">{t("rows.start")}</th>
              <td>{tr(`startTypes.${a.start_type}`)}</td>
              <td>{tr(`startTypes.${b.start_type}`)}</td>
              <td />
            </tr>
            {rows.map((row) => {
              const winner = row.direction ? better(row.a, row.b, row.direction) : null;
              return (
                <tr key={row.id}>
                  <th scope="row">{t(`rows.${row.id}` as "rows.total")}</th>
                  <td className={winnerClass("a", winner)}>{row.a != null ? row.format(row.a) : "—"}</td>
                  <td className={winnerClass("b", winner)}>{row.b != null ? row.format(row.b) : "—"}</td>
                  <td>{row.delta && row.a != null && row.b != null ? row.delta(row.b - row.a) : ""}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="compare-note">{t("differenceHint")}</p>
      </Card>

      <Card title={t("lapsTitle")}>
        <ChartFrame
          height={240}
          caption={t("lapsCaption")}
          legend={[
            { label: nameA, color: A_COLOR },
            { label: nameB, color: B_COLOR },
          ]}
        >
          <LineChart data={laps} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid {...gridProps} />
            <XAxis dataKey="lap" {...axisProps} interval="preserveStartEnd" minTickGap={12} />
            <YAxis domain={secondsDomain} tickFormatter={(ms: number) => fmt.seconds(ms, 1)} width={44} {...axisProps} />
            <Tooltip
              cursor={cursorProps}
              content={<ChartTooltip formatValue={(ms) => `${fmt.seconds(ms)} s`} formatLabel={(lap) => tt("efforts.lapN", { n: lap })} />}
            />
            <Line dataKey="a" name={nameA} stroke={A_COLOR} strokeWidth={2} dot={{ r: 2.5 }} isAnimationActive={false} />
            <Line dataKey="b" name={nameB} stroke={B_COLOR} strokeWidth={2} dot={{ r: 2.5 }} isAnimationActive={false} />
          </LineChart>
        </ChartFrame>
      </Card>

      <Card title={t("gapTitle")}>
        <ChartFrame
          height={200}
          isEmpty={gap.length === 0}
          emptyMessage={t("gapEmpty")}
          caption={t("gapCaption", { a: nameA, b: nameB })}
        >
          <LineChart data={gap} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid {...gridProps} />
            <XAxis dataKey="lap" {...axisProps} interval="preserveStartEnd" minTickGap={12} />
            <YAxis tickFormatter={(ms: number) => fmt.deltaSeconds(ms, 1)} width={52} {...axisProps} />
            <ReferenceLine y={0} stroke="var(--color-border-strong)" />
            <Tooltip
              cursor={cursorProps}
              content={<ChartTooltip formatValue={(ms) => `${fmt.deltaSeconds(ms)} s`} formatLabel={(lap) => tt("efforts.lapN", { n: lap })} />}
            />
            <Line dataKey="deltaMs" name={t("gapSeries")} stroke="var(--chart-2)" strokeWidth={2} dot={{ r: 2.5 }} isAnimationActive={false} />
          </LineChart>
        </ChartFrame>
      </Card>

      {splits.length > 0 && (
        <Card title={t("splitsTitle")}>
          <ChartFrame
            height={220}
            caption={tt("efforts.splitsCaption")}
            legend={[
              { label: nameA, color: A_COLOR },
              { label: nameB, color: B_COLOR },
            ]}
          >
            <BarChart data={splits} margin={{ top: 8, right: 4, left: 0, bottom: 0 }}>
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="n" {...axisProps} interval="preserveStartEnd" minTickGap={12} />
              <YAxis domain={secondsDomain} tickFormatter={(ms: number) => fmt.seconds(ms, 1)} width={44} {...axisProps} />
              <Tooltip
                cursor={{ fill: "var(--chart-grid)", fillOpacity: 0.4, ...cursorProps }}
                content={
                  <ChartTooltip
                    formatValue={(ms) => `${fmt.seconds(ms)} s`}
                    formatLabel={(n) => {
                      const split = splits.find((row) => row.n === Number(n));
                      const [from, to] = (split?.label ?? "→").split("→");
                      return tt("efforts.split", { from, to });
                    }}
                  />
                }
              />
              <Bar dataKey="a" name={nameA} fill={A_COLOR} isAnimationActive={false} radius={[3, 3, 0, 0]} />
              <Bar dataKey="b" name={nameB} fill={B_COLOR} isAnimationActive={false} radius={[3, 3, 0, 0]} />
            </BarChart>
          </ChartFrame>
        </Card>
      )}
    </div>
  );
}
