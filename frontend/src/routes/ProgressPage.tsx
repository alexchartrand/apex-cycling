import { useMemo, useState } from "react";
import { BarChart3, LineChart as LineChartIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Brush, CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from "recharts";
import { axisProps, ChartFrame, ChartTooltip, cursorProps, gridProps, secondsDomain } from "../components/charts";
import { Card, EmptyState, Input, PageHeader, Select, SkeletonGroup } from "../components/ui";
import { useActiveAthlete } from "../features/athletes/useActiveAthlete";
import type { ProgressionParams } from "../features/training/types";
import { useProgression, useTracks } from "../features/training/useTraining";
import { parseLocalDate } from "../i18n/format";
import { useFormat } from "../i18n/useFormat";
import "./ProgressPage.css";

const VIEW_PREFIX = "view:";

export function ProgressPage() {
  const { t } = useTranslation(["training", "shell", "common"]);
  const fmt = useFormat();
  const athleteId = useActiveAthlete().data?.id ?? "";
  const tracks = useTracks(athleteId);

  const [trackId, setTrackId] = useState("");
  const [metricKey, setMetricKey] = useState("lap_time");
  const [distanceM, setDistanceM] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");

  const selectedTrack = tracks.data?.find((track) => track.id === trackId);

  const params: ProgressionParams | null = useMemo(() => {
    if (!trackId) return null;
    const base = { from: fromDate || undefined, to: toDate || undefined };
    if (metricKey === "lap_time") return { ...base, metric: "lap_time", track_id: trackId };
    if (metricKey === "custom_distance") {
      const distance = Number(distanceM);
      if (!distanceM || Number.isNaN(distance) || distance <= 0) return null;
      return { ...base, metric: "custom_distance", track_id: trackId, distance_m: distance };
    }
    if (metricKey.startsWith(VIEW_PREFIX)) {
      return { ...base, metric: "view", track_view_id: metricKey.slice(VIEW_PREFIX.length) };
    }
    return null;
  }, [trackId, metricKey, distanceM, fromDate, toDate]);

  const progression = useProgression(athleteId, params);
  // Numeric x (epoch ms) so the axis is a true time scale: a three-week
  // break looks like one, instead of sitting as close as consecutive days.
  const chartData = (progression.data ?? []).map((point) => ({
    t: parseLocalDate(point.event_date).getTime(),
    timeMs: point.time_ms,
  }));

  return (
    <>
      <PageHeader title={t("progress.title")} description={t("progress.description")} />

      {tracks.isLoading && <SkeletonGroup lines={4} />}
      {tracks.isError && <p role="alert">{t("common:loadError")}</p>}
      {tracks.data?.length === 0 && (
        <EmptyState icon={<BarChart3 aria-hidden />} title={t("progress.noTracksTitle")} description={t("progress.noTracks")} />
      )}

      {tracks.data && tracks.data.length > 0 && (
        <div className="progress-page">
          <Card className="progress-page__filters">
            <Select
              label={t("progress.track")}
              value={trackId}
              onChange={(e) => {
                setTrackId(e.target.value);
                setMetricKey("lap_time");
              }}
            >
              <option value="">{t("progress.selectTrack")}</option>
              {tracks.data.map((track) => (
                <option key={track.id} value={track.id}>
                  {track.name}
                </option>
              ))}
            </Select>
            <Select
              label={t("progress.metric")}
              value={metricKey}
              onChange={(e) => setMetricKey(e.target.value)}
              disabled={!trackId}
            >
              <option value="lap_time">{t("progress.metrics.lapTime")}</option>
              <option value="custom_distance">{t("progress.metrics.customDistance")}</option>
              {selectedTrack?.views.map((view) => (
                <option key={view.id} value={`${VIEW_PREFIX}${view.id}`}>
                  {view.name}
                </option>
              ))}
            </Select>
            {metricKey === "custom_distance" && (
              <Input
                label={t("progress.distance")}
                type="number"
                min={1}
                inputMode="numeric"
                suffix="m"
                value={distanceM}
                onChange={(e) => setDistanceM(e.target.value)}
                placeholder="150"
              />
            )}
            <Input label={t("progress.from")} type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
            <Input label={t("progress.to")} type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
          </Card>

          <Card>
            {!params && <EmptyState compact icon={<LineChartIcon aria-hidden />} title={t("progress.pickTrack")} />}
            {params && progression.isLoading && <SkeletonGroup lines={6} />}
            {params && progression.isError && <p role="alert">{t("progress.loadError")}</p>}
            {params && progression.data && (
              <ChartFrame
                height={340}
                isEmpty={chartData.length === 0}
                emptyMessage={t("progress.noData")}
                legend={[{ label: t("progress.seriesLabel"), color: "var(--chart-1)" }]}
                caption={chartData.length > 1 ? t("progress.chartCaption") : undefined}
              >
                <LineChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid {...gridProps} />
                  <XAxis
                    dataKey="t"
                    type="number"
                    scale="time"
                    domain={["dataMin", "dataMax"]}
                    tickFormatter={(t: number) => fmt.date(new Date(t), "dayMonth")}
                    minTickGap={32}
                    {...axisProps}
                  />
                  <YAxis
                    domain={secondsDomain}
                    tickFormatter={(ms: number) => fmt.lapTime(ms)}
                    width={72}
                    {...axisProps}
                  />
                  <Tooltip
                    cursor={cursorProps}
                    content={<ChartTooltip formatValue={(ms) => fmt.lapTime(ms)} formatLabel={(t) => fmt.date(new Date(Number(t)), "medium")} />}
                  />
                  <Line
                    type="linear"
                    dataKey="timeMs"
                    name={t("progress.seriesLabel")}
                    stroke="var(--chart-1)"
                    strokeWidth={2}
                    dot={{ r: 3, fill: "var(--chart-1)", strokeWidth: 0 }}
                    activeDot={{ r: 5 }}
                  />
                  {chartData.length > 1 && (
                    <Brush
                      dataKey="t"
                      height={26}
                      stroke="var(--color-border-strong)"
                      fill="var(--color-surface-2)"
                      travellerWidth={10}
                      tickFormatter={(t: number) => fmt.date(new Date(t), "dayMonth")}
                    />
                  )}
                </LineChart>
              </ChartFrame>
            )}
          </Card>
        </div>
      )}
    </>
  );
}
