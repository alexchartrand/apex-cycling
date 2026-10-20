import { useMemo, useState } from "react";
import { Area, AreaChart, Brush, CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from "recharts";
import { useTranslation } from "react-i18next";
import { axisProps, ChartFrame, ChartTooltip, cursorProps, gridProps } from "../../components/charts";
import { Card, Checkbox, SegmentedControl } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { availableChannels, canUseDistance, toRows, windowAverage, type Channel, type XAxisMode } from "./streamChart";
import type { ActivityStreams } from "./types";

const CHANNEL_STYLE: Record<Channel, { color: string; height: number }> = {
  power: { color: "var(--chart-1)", height: 200 },
  heartRate: { color: "var(--chart-4)", height: 120 },
  cadence: { color: "var(--chart-3)", height: 120 },
  speed: { color: "var(--chart-2)", height: 120 },
  altitude: { color: "var(--chart-5)", height: 100 },
};

const DECIMALS: Record<Channel, number> = { power: 0, heartRate: 0, cadence: 0, speed: 1, altitude: 0 };

/**
 * The recording over time or distance, one small chart per channel sharing an x
 * axis. The strip under them zooms all of them at once; the averages beside
 * the legend follow the zoomed part.
 */
export function StreamChart({ streams }: { streams: ActivityStreams }) {
  const { t } = useTranslation("activities");
  const fmt = useFormat();
  const channels = availableChannels(streams);
  const [mode, setMode] = useState<XAxisMode>("time");
  const [hidden, setHidden] = useState<Set<Channel>>(new Set());
  const [range, setRange] = useState<[number, number] | null>(null);

  const distanceOk = canUseDistance(streams);
  const effectiveMode: XAxisMode = distanceOk ? mode : "time";
  const rows = useMemo(() => toRows(streams, effectiveMode), [streams, effectiveMode]);
  const overview = channels[0];
  const shown = channels.filter((channel) => !hidden.has(channel));

  // The brush works in row indexes; keep the selection when the data is the same length.
  const start = Math.min(range?.[0] ?? 0, Math.max(rows.length - 1, 0));
  const end = Math.min(range?.[1] ?? rows.length - 1, rows.length - 1);
  const visible = rows.slice(start, end + 1);
  const from = visible[0]?.x ?? 0;
  const to = visible[visible.length - 1]?.x ?? 0;
  const zoomed = range !== null && (start > 0 || end < rows.length - 1);

  const formatX = (x: number) => (effectiveMode === "time" ? fmt.duration(x) : `${fmt.number(x, 1)} km`);
  const labels: Record<Channel, string> = {
    power: t("activity.chart.power"),
    heartRate: t("activity.chart.heartRate"),
    cadence: t("activity.chart.cadence"),
    speed: t("activity.chart.speed"),
    altitude: t("activity.chart.altitude"),
  };

  if (channels.length === 0 || rows.length < 2) {
    return (
      <Card title={t("activity.chart.title")}>
        <p className="ui-card__hint">{t("activity.chart.noStreams")}</p>
      </Card>
    );
  }

  return (
    <Card
      title={t("activity.chart.title")}
      actions={
        distanceOk ? (
          <SegmentedControl
            size="sm"
            aria-label={t("activity.chart.xTime")}
            value={mode}
            onChange={(next) => {
              setMode(next);
              setRange(null);
            }}
            options={[
              { value: "time", label: t("activity.chart.xTime") },
              { value: "distance", label: t("activity.chart.xDistance") },
            ]}
          />
        ) : undefined
      }
    >
      <div className="stream-chart__channels">
        {channels.map((channel) => {
          const average = windowAverage(rows, channel, from, to);
          return (
            <label key={channel} className="stream-chart__channel">
              <Checkbox
                checked={!hidden.has(channel)}
                onChange={() =>
                  setHidden((current) => {
                    const next = new Set(current);
                    if (next.has(channel)) next.delete(channel);
                    else next.add(channel);
                    return next;
                  })
                }
                label={
                  <span>
                    <span className="stream-chart__swatch" style={{ background: CHANNEL_STYLE[channel].color }} />
                    {labels[channel]}
                    {average != null && (
                      <span className="stream-chart__average">
                        {zoomed ? `${t("activity.chart.selection")} ` : "⌀ "}
                        {fmt.number(average, DECIMALS[channel])}
                      </span>
                    )}
                  </span>
                }
              />
            </label>
          );
        })}
      </div>

      <div className="stream-chart__stack">
        {shown.map((channel) => {
          const { color, height } = CHANNEL_STYLE[channel];
          const isArea = channel === "altitude";
          const Chart = isArea ? AreaChart : LineChart;
          return (
            <ChartFrame key={channel} height={height}>
              <Chart data={visible} syncId="activity-streams" margin={{ top: 4, right: 12, bottom: 0, left: 0 }}>
                <CartesianGrid {...gridProps} />
                <XAxis {...axisProps} dataKey="x" type="number" domain={[from, to]} tickFormatter={formatX} hide={channel !== shown[shown.length - 1]} allowDataOverflow />
                <YAxis {...axisProps} width={44} tickFormatter={(v: number) => fmt.number(v, DECIMALS[channel])} />
                <Tooltip
                  cursor={cursorProps}
                  content={
                    <ChartTooltip
                      formatLabel={(label) => formatX(Number(label))}
                      formatValue={(value) => fmt.number(value, DECIMALS[channel])}
                    />
                  }
                />
                {isArea ? (
                  <Area type="monotone" dataKey={channel} name={labels[channel]} stroke={color} fill={color} fillOpacity={0.18} strokeWidth={1.5} dot={false} isAnimationActive={false} connectNulls />
                ) : (
                  <Line type="monotone" dataKey={channel} name={labels[channel]} stroke={color} strokeWidth={1.5} dot={false} isAnimationActive={false} connectNulls />
                )}
              </Chart>
            </ChartFrame>
          );
        })}
      </div>

      <ChartFrame height={64} caption={t("activity.chart.zoomHint")}>
        <LineChart data={rows} margin={{ top: 2, right: 12, bottom: 0, left: 44 }}>
          <XAxis dataKey="x" type="number" hide domain={["dataMin", "dataMax"]} />
          {overview && <Line type="monotone" dataKey={overview} stroke="var(--color-text-3)" strokeWidth={1} dot={false} isAnimationActive={false} connectNulls />}
          <Brush
            dataKey="x"
            height={28}
            stroke="var(--color-border-strong)"
            fill="var(--color-surface-2)"
            travellerWidth={10}
            tickFormatter={formatX}
            startIndex={start}
            endIndex={end}
            onChange={(next) => {
              if (next.startIndex != null && next.endIndex != null) setRange([next.startIndex, next.endIndex]);
            }}
          />
        </LineChart>
      </ChartFrame>
    </Card>
  );
}
