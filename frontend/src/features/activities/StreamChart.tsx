import { useMemo, useState } from "react";
import { Area, AreaChart, Brush, CartesianGrid, Line, LineChart, ReferenceArea, Tooltip, XAxis, YAxis } from "recharts";
import { useTranslation } from "react-i18next";
import { axisProps, ChartFrame, ChartTooltip, cursorProps, gridProps } from "../../components/charts";
import { Card, Checkbox, SegmentedControl } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import type { SessionOverlay } from "./sessionOverlay";
import {
  availableChannels,
  canUseDistance,
  spanIndexes,
  toRows,
  windowAverage,
  withEstimatedCadence,
  withLapSpeed,
  withOverlayChannels,
  type Channel,
  type XAxisMode,
} from "./streamChart";
import type { ActivityStreams } from "./types";

const CHANNEL_STYLE: Record<Channel, { color: string; height: number }> = {
  power: { color: "var(--chart-1)", height: 200 },
  heartRate: { color: "var(--chart-4)", height: 120 },
  cadence: { color: "var(--chart-3)", height: 120 },
  speed: { color: "var(--chart-2)", height: 120 },
  altitude: { color: "var(--chart-5)", height: 100 },
};

const DECIMALS: Record<Channel, number> = { power: 0, heartRate: 0, cadence: 0, speed: 1, altitude: 0 };

const SQORZ_SPEED_COLOR = "var(--color-text)";

/**
 * The recording over time or distance, one small chart per channel sharing an x
 * axis. The strip under them zooms all of them at once; the averages beside
 * the legend follow the zoomed part.
 *
 * With a `session` (a recording linked to a sqorz session, on its page) and
 * time on the x axis, the efforts are shaded, sqorz's lap speed steps along
 * the speed chart, the cadence the gear implies at the recorded speed follows
 * the cadence chart (dashed), the axis reads the session's clock and the chart
 * opens on the session's span.
 */
export function StreamChart({ streams, session }: { streams: ActivityStreams; session?: SessionOverlay }) {
  const { t } = useTranslation("activities");
  const fmt = useFormat();
  const [mode, setMode] = useState<XAxisMode>("time");
  const [hidden, setHidden] = useState<Set<Channel>>(new Set());
  const [range, setRange] = useState<[number, number] | null>(null);

  const distanceOk = canUseDistance(streams);
  const effectiveMode: XAxisMode = distanceOk ? mode : "time";
  const overlay = effectiveMode === "time" ? session : undefined;
  const lapSpeed = overlay !== undefined && overlay.laps.length > 0;
  const estCadence =
    overlay !== undefined && streams.speed_mps !== null && (overlay.gearing.sessionDevelopmentM !== null || overlay.gearing.efforts.length > 0);
  const channels = withOverlayChannels(availableChannels(streams), [...(lapSpeed ? ["speed" as const] : []), ...(estCadence ? ["cadence" as const] : [])]);
  const rows = useMemo(() => {
    let result = toRows(streams, effectiveMode);
    if (overlay && lapSpeed) result = withLapSpeed(result, overlay.laps);
    if (overlay && estCadence) result = withEstimatedCadence(result, overlay.gearing);
    return result;
  }, [streams, effectiveMode, overlay, lapSpeed, estCadence]);
  const shown = channels.filter((channel) => !hidden.has(channel));
  const sessionRange = useMemo(() => (overlay ? spanIndexes(rows, overlay) : null), [rows, overlay]);

  // The brush works in row indexes; keep the selection when the data is the same length.
  const selected = range ?? sessionRange;
  const start = Math.min(selected?.[0] ?? 0, Math.max(rows.length - 1, 0));
  const end = Math.min(selected?.[1] ?? rows.length - 1, rows.length - 1);
  const visible = rows.slice(start, end + 1);
  const from = visible[0]?.x ?? 0;
  const to = visible[visible.length - 1]?.x ?? 0;
  const zoomed = start > 0 || end < rows.length - 1;

  const clock = (x: number, seconds: boolean) =>
    new Intl.DateTimeFormat(fmt.locale, { hour: "numeric", minute: "2-digit", second: seconds ? "2-digit" : undefined }).format(
      new Date(overlay!.clockStartMs + x * 1000),
    );
  const formatX = (x: number) => (effectiveMode === "distance" ? `${fmt.number(x, 1)} km` : overlay ? clock(x, false) : fmt.duration(x));
  const formatLabel = (x: number) => (overlay ? clock(x, true) : formatX(x));
  // Series the session adds beside a channel: each gets a legend entry with its average.
  const extras = [
    lapSpeed && !hidden.has("speed") && { key: "sqorzSpeed" as const, channel: "speed" as const, label: t("activity.chart.sqorzSpeed"), color: SQORZ_SPEED_COLOR, dashed: false },
    estCadence && !hidden.has("cadence") && { key: "estCadence" as const, channel: "cadence" as const, label: t("activity.chart.estCadence"), color: CHANNEL_STYLE.cadence.color, dashed: true },
  ].filter((extra) => extra !== false);
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
        {extras.map((extra) => {
          const average = windowAverage(rows, extra.key, from, to);
          return (
            <span key={extra.key} className="stream-chart__channel">
              <span className={extra.dashed ? "stream-chart__swatch stream-chart__swatch--dashed" : "stream-chart__swatch"} style={{ color: extra.color, background: extra.dashed ? undefined : extra.color }} />
              {extra.label}
              {average != null && (
                <span className="stream-chart__average">
                  {zoomed ? `${t("activity.chart.selection")} ` : "⌀ "}
                  {fmt.number(average, DECIMALS[extra.channel])}
                </span>
              )}
            </span>
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
                      formatLabel={(label) => formatLabel(Number(label))}
                      formatValue={(value) => fmt.number(value, DECIMALS[channel])}
                    />
                  }
                />
                {overlay?.bands.map((band) => (
                  <ReferenceArea
                    key={band.index}
                    x1={band.fromS}
                    x2={band.toS}
                    ifOverflow="hidden"
                    fill="var(--color-text-3)"
                    fillOpacity={0.12}
                    stroke="none"
                    label={
                      channel === shown[0]
                        ? { value: band.label ?? t("activity.chart.effort", { n: band.index }), position: "insideTopLeft", fill: "var(--color-text-2)", fontSize: 10 }
                        : undefined
                    }
                  />
                ))}
                {isArea ? (
                  <Area type="monotone" dataKey={channel} name={labels[channel]} stroke={color} fill={color} fillOpacity={0.18} strokeWidth={1.5} dot={false} isAnimationActive={false} connectNulls />
                ) : (
                  <Line type="monotone" dataKey={channel} name={labels[channel]} stroke={color} strokeWidth={1.5} dot={false} isAnimationActive={false} connectNulls />
                )}
                {extras
                  .filter((extra) => extra.channel === channel)
                  .map((extra) => (
                    <Line
                      key={extra.key}
                      type={extra.dashed ? "monotone" : "stepAfter"}
                      dataKey={extra.key}
                      name={extra.label}
                      stroke={extra.color}
                      strokeWidth={extra.dashed ? 1.5 : 2}
                      strokeDasharray={extra.dashed ? "4 3" : undefined}
                      dot={false}
                      isAnimationActive={false}
                    />
                  ))}
              </Chart>
            </ChartFrame>
          );
        })}
      </div>

      {/* Just the brush handles: an empty chart carrying the rows they select from. */}
      <ChartFrame height={32} caption={t("activity.chart.zoomHint")}>
        <LineChart data={rows} margin={{ top: 2, right: 12, bottom: 0, left: 44 }}>
          <XAxis dataKey="x" type="number" hide domain={["dataMin", "dataMax"]} />
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
