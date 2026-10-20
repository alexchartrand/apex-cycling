import { useMemo, useState } from "react";
import { BarChart3, LineChart as LineChartIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Brush, CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from "recharts";
import { axisProps, ChartFrame, ChartTooltip, cursorProps, gridProps, secondsDomain } from "../components/charts";
import { Card, EmptyState, Input, PageHeader, Select, SkeletonGroup } from "../components/ui";
import { FitnessCard } from "../features/activities/FitnessCard";
import "../features/activities/Activities.css";
import { useActiveAthlete } from "../features/athletes/useActiveAthlete";
import {
  availableEvents,
  buildProgressionParams,
  defaultStart,
  EVENT_PREFIX,
  personalBestLine,
  recordSessions,
  startTypeApplies,
  VIEW_PREFIX,
  type StartChoice,
} from "../features/training/progression";
import { useProgression, useTracks } from "../features/training/useTraining";
import { parseLocalDate } from "../i18n/format";
import { useFormat } from "../i18n/useFormat";
import "./ProgressPage.css";

export function ProgressPage() {
  const { t } = useTranslation(["training", "shell", "common"]);
  const { t: tr } = useTranslation("records");
  const fmt = useFormat();
  const athleteId = useActiveAthlete().data?.id ?? "";
  const tracks = useTracks(athleteId);

  const [trackId, setTrackId] = useState("");
  const [metricKey, setMetricKey] = useState("lap_time");
  const [distanceM, setDistanceM] = useState("");
  const [start, setStart] = useState<StartChoice>("any");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");

  const selectedTrack = tracks.data?.find((track) => track.id === trackId);

  const params = useMemo(
    () => buildProgressionParams({ track: selectedTrack, metricKey, distance: distanceM, start, from: fromDate, to: toDate }),
    [selectedTrack, metricKey, distanceM, start, fromDate, toDate],
  );
  const events = availableEvents(selectedTrack);
  const visibleViews = selectedTrack?.views.filter((view) => !view.hidden) ?? [];

  function chooseMetric(next: string) {
    setMetricKey(next);
    setStart(defaultStart(next));
  }

  const progression = useProgression(athleteId, params);
  // Numeric x (epoch ms) so the axis is a true time scale: a three-week
  // break looks like one, instead of sitting as close as consecutive days.
  const points = progression.data ?? [];
  const records = recordSessions(points);
  const pbByTime = new Map(personalBestLine(points.map((p) => ({ t: parseLocalDate(p.event_date).getTime(), timeMs: p.time_ms }))).map((p) => [p.t, p.pbMs]));
  const chartData = points.map((point) => {
    const time = parseLocalDate(point.event_date).getTime();
    return { t: time, timeMs: point.time_ms, pbMs: pbByTime.get(time), isRecord: records.has(point.external_event_id) };
  });

  return (
    <>
      <PageHeader title={t("progress.title")} description={t("progress.description")} />

      {athleteId !== "" && <FitnessCard athleteId={athleteId} />}

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
                chooseMetric("lap_time");
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
              onChange={(e) => chooseMetric(e.target.value)}
              disabled={!trackId}
              hint={trackId && events.length === 0 ? t("progress.eventsNeedLength") : undefined}
            >
              <option value="lap_time">{t("progress.metrics.lapTime")}</option>
              <option value="custom_distance">{t("progress.metrics.customDistance")}</option>
              {events.length > 0 && (
                <optgroup label={t("progress.standardEvents")}>
                  {events.map((key) => (
                    <option key={key} value={`${EVENT_PREFIX}${key}`}>
                      {tr(`events.${key}`)}
                    </option>
                  ))}
                </optgroup>
              )}
              {visibleViews.length > 0 && (
                <optgroup label={t("progress.views")}>
                  {visibleViews.map((view) => (
                    <option key={view.id} value={`${VIEW_PREFIX}${view.id}`}>
                      {view.name}
                    </option>
                  ))}
                </optgroup>
              )}
            </Select>
            {startTypeApplies(metricKey, selectedTrack) && (
              <Select label={t("progress.start")} value={start} onChange={(e) => setStart(e.target.value as StartChoice)}>
                <option value="any">{t("progress.startAny")}</option>
                <option value="standing">{tr("startTypes.standing")}</option>
                <option value="flying">{tr("startTypes.flying")}</option>
              </Select>
            )}
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
                legend={[
                  { label: t("progress.seriesLabel"), color: "var(--chart-1)" },
                  { label: t("progress.personalBest"), color: "var(--chart-3)", dashed: true },
                ]}
                caption={
                  chartData.length > 1
                    ? `${t("progress.chartCaption")}${records.size > 0 ? ` ${t("progress.recordDot")}` : ""}`
                    : undefined
                }
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
                    type="stepAfter"
                    dataKey="pbMs"
                    name={t("progress.personalBest")}
                    stroke="var(--chart-3)"
                    strokeWidth={2}
                    strokeDasharray="6 4"
                    dot={false}
                    activeDot={false}
                    isAnimationActive={false}
                  />
                  <Line
                    type="linear"
                    dataKey="timeMs"
                    name={t("progress.seriesLabel")}
                    stroke="var(--chart-1)"
                    strokeWidth={2}
                    dot={(props: { cx?: number; cy?: number; index?: number; payload?: { isRecord: boolean } }) =>
                      props.cx == null || props.cy == null ? <g key={props.index} /> : props.payload?.isRecord ? (
                        <circle key={props.index} cx={props.cx} cy={props.cy} r={5} fill="var(--color-marker)" stroke="var(--color-surface)" strokeWidth={1.5} />
                      ) : (
                        <circle key={props.index} cx={props.cx} cy={props.cy} r={3} fill="var(--chart-1)" />
                      )
                    }
                    activeDot={{ r: 5 }}
                    isAnimationActive={false}
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
