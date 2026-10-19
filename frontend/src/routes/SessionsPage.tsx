import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Button, Card, Select } from "../components/ui";
import { useMyAthlete } from "../features/athletes/useAthlete";
import { formatKm, formatMs } from "../features/training/format";
import { TrackSchema } from "../features/training/TrackSchema";
import type { LapDetail, SessionSummary, TrackLoopSummary, TrackSessionDetail } from "../features/training/types";
import { useSessionDetail, useSessions, useTracks } from "../features/training/useTraining";
import "./SessionsPage.css";

const FLYING_200_VIEW_NAME = "200m";
const LAP_DISTANCE_M = 250;

type ChartMetric = "lapTime" | "flying200" | "none";

const CHART_METRIC_OPTIONS: { value: ChartMetric; label: string }[] = [
  { value: "lapTime", label: "Lap time" },
  { value: "flying200", label: "Flying 200 time" },
  { value: "none", label: "None" },
];

const CHART_METRIC_CONFIG: Record<Exclude<ChartMetric, "none">, { dataKey: "lapTimeMs" | "flying200Ms"; label: string; color: string }> = {
  lapTime: { dataKey: "lapTimeMs", label: "Lap time", color: "var(--accent)" },
  flying200: { dataKey: "flying200Ms", label: "Flying 200", color: "var(--chart-3)" },
};

function sessionLabel(session: SessionSummary, sessions: SessionSummary[]): string {
  const sameDate = sessions.filter((s) => s.event_date === session.event_date);
  if (sameDate.length <= 1) return session.event_date;
  const index = sameDate.findIndex((s) => s.external_event_id === session.external_event_id);
  return `${session.event_date} - ${index + 1}`;
}

function lapLabel(lap: LapDetail, index: number): string {
  return lap.start_number != null ? `${lap.start_number}` : `Lap ${index + 1}`;
}

function bestLap(
  laps: LapDetail[],
  getValue: (lap: LapDetail) => number | null | undefined,
): { lap: LapDetail; index: number; value: number } | null {
  let best: { lap: LapDetail; index: number; value: number } | null = null;
  laps.forEach((lap, index) => {
    const value = getValue(lap);
    if (value == null) return;
    if (best == null || value < best.value) best = { lap, index, value };
  });
  return best;
}

function flying200Ms(lap: LapDetail): number | null | undefined {
  return lap.views.find((view) => view.name === FLYING_200_VIEW_NAME)?.time_ms;
}

function formatChartSeconds(ms: number | null | undefined): string {
  if (ms == null) return "";
  return (ms / 1000).toFixed(3);
}

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
  const isSelected = lapId != null && lapId === selectedLapId;
  return (
    <circle
      cx={cx}
      cy={cy}
      r={isSelected ? 6 : 3}
      fill={color}
      stroke={isSelected ? "var(--color-text)" : "none"}
      strokeWidth={isSelected ? 2 : 0}
    />
  );
}

function LapChart({
  laps,
  selectedLapId,
  leftMetric,
  rightMetric,
}: {
  laps: LapDetail[];
  selectedLapId: string | null;
  leftMetric: ChartMetric;
  rightMetric: ChartMetric;
}) {
  const activeMetrics = [leftMetric, rightMetric].filter(
    (metric): metric is Exclude<ChartMetric, "none"> => metric !== "none",
  );

  const data = laps
    .map((lap, index) => ({
      lapId: lap.lap_id,
      label: lapLabel(lap, index),
      lapTimeMs: lap.whole_lap_time_ms ?? null,
      flying200Ms: flying200Ms(lap) ?? null,
    }))
    .filter((row) => activeMetrics.some((metric) => row[CHART_METRIC_CONFIG[metric].dataKey] != null));

  if (activeMetrics.length === 0 || data.length === 0) {
    return (
      <div className="session-track__chart-empty">
        {activeMetrics.length === 0
          ? "Choose a metric for at least one axis to see a chart."
          : "No data available for the selected metrics."}
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ left: 12, right: 12 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="label" />
        {leftMetric !== "none" && (
          <YAxis
            yAxisId="left"
            domain={["dataMin - 200", "dataMax + 200"]}
            tickFormatter={formatChartSeconds}
            width={64}
          />
        )}
        {rightMetric !== "none" && (
          <YAxis
            yAxisId="right"
            orientation="right"
            domain={["dataMin - 200", "dataMax + 200"]}
            tickFormatter={formatChartSeconds}
            width={64}
          />
        )}
        <Tooltip formatter={(value, name) => [formatChartSeconds(typeof value === "number" ? value : null), name]} />
        {leftMetric !== "none" && (
          <Line
            yAxisId="left"
            type="monotone"
            dataKey={CHART_METRIC_CONFIG[leftMetric].dataKey}
            name={CHART_METRIC_CONFIG[leftMetric].label}
            stroke={CHART_METRIC_CONFIG[leftMetric].color}
            dot={(props: any) => (
              <HighlightDot
                key={props.payload?.lapId ?? props.index}
                {...props}
                lapId={props.payload?.lapId}
                selectedLapId={selectedLapId}
                color={CHART_METRIC_CONFIG[leftMetric].color}
              />
            )}
          />
        )}
        {rightMetric !== "none" && (
          <Line
            yAxisId="right"
            type="monotone"
            dataKey={CHART_METRIC_CONFIG[rightMetric].dataKey}
            name={CHART_METRIC_CONFIG[rightMetric].label}
            stroke={CHART_METRIC_CONFIG[rightMetric].color}
            dot={(props: any) => (
              <HighlightDot
                key={props.payload?.lapId ?? props.index}
                {...props}
                lapId={props.payload?.lapId}
                selectedLapId={selectedLapId}
                color={CHART_METRIC_CONFIG[rightMetric].color}
              />
            )}
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}

function TrackSection({
  track,
  loops,
  lengthM,
}: {
  track: TrackSessionDetail;
  loops: TrackLoopSummary[];
  lengthM: number | null | undefined;
}) {
  const [selectedLapId, setSelectedLapId] = useState<string | null>(null);
  const [leftMetric, setLeftMetric] = useState<ChartMetric>("lapTime");
  const [rightMetric, setRightMetric] = useState<ChartMetric>("flying200");
  const chartRef = useRef<HTMLDivElement>(null);

  const bestLapTime = useMemo(() => bestLap(track.laps, (lap) => lap.whole_lap_time_ms), [track.laps]);
  const bestFlying200 = useMemo(() => bestLap(track.laps, flying200Ms), [track.laps]);
  const totalLaps = track.laps.length;
  const totalDistanceKm = (totalLaps * LAP_DISTANCE_M) / 1000;

  function selectLap(lapId: string) {
    setSelectedLapId(lapId);
    chartRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  return (
    <section>
      <div className="session-track__stats">
        <div className="session-track__stats-row session-track__stats-row--totals">
          <div className="session-track__stat">
            <span className="session-track__stat-value">{totalLaps}</span>
            <span className="session-track__stat-label">Total laps</span>
          </div>
          <div className="session-track__stat">
            <span className="session-track__stat-value">{formatKm(totalDistanceKm)}</span>
            <span className="session-track__stat-label">Total distance</span>
          </div>
        </div>
        <div className="session-track__stats-row">
          <div className="session-track__stat">
            <div className="session-track__stat-row">
              <span className="session-track__stat-value">{formatMs(bestLapTime?.value)}</span>
              {bestLapTime && (
                <Button type="button" scale="sm" onClick={() => selectLap(bestLapTime.lap.lap_id)}>
                  {lapLabel(bestLapTime.lap, bestLapTime.index)}
                </Button>
              )}
            </div>
            <span className="session-track__stat-label">Best lap time</span>
          </div>
          <div className="session-track__stat">
            <div className="session-track__stat-row">
              <span className="session-track__stat-value">{formatMs(bestFlying200?.value)}</span>
              {bestFlying200 && (
                <Button type="button" scale="sm" onClick={() => selectLap(bestFlying200.lap.lap_id)}>
                  {lapLabel(bestFlying200.lap, bestFlying200.index)}
                </Button>
              )}
            </div>
            <span className="session-track__stat-label">Best flying 200 time</span>
          </div>
        </div>
      </div>
      <div className="session-track__controls">
        <Select
          scale="sm"
          label="Left axis"
          value={leftMetric}
          onChange={(e) => setLeftMetric(e.target.value as ChartMetric)}
        >
          {CHART_METRIC_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
        <Select
          scale="sm"
          label="Right axis"
          value={rightMetric}
          onChange={(e) => setRightMetric(e.target.value as ChartMetric)}
        >
          {CHART_METRIC_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
      </div>
      <div ref={chartRef} className="session-track__chart">
        <LapChart laps={track.laps} selectedLapId={selectedLapId} leftMetric={leftMetric} rightMetric={rightMetric} />
      </div>
      <TrackSchema loops={loops} lengthM={lengthM} />
    </section>
  );
}

function SessionDetail({ athleteId, eventId }: { athleteId: string; eventId: string }) {
  const detail = useSessionDetail(athleteId, eventId);
  const tracks = useTracks(athleteId);

  return (
    <>
      {detail.isLoading && <p>Loading…</p>}
      {detail.isError && <p role="alert">Could not load this session.</p>}
      {detail.data?.tracks.map((track) => (
        <TrackSection
          key={track.track_id}
          track={track}
          loops={tracks.data?.find((t) => t.id === track.track_id)?.loops ?? []}
          lengthM={tracks.data?.find((t) => t.id === track.track_id)?.length_m}
        />
      ))}
    </>
  );
}

export function SessionsPage() {
  const { eventId } = useParams();
  const navigate = useNavigate();
  const athlete = useMyAthlete();
  const sessions = useSessions(athlete.data?.id ?? "");

  const selectedEventId = useMemo(() => {
    if (!sessions.data || sessions.data.length === 0) return "";
    if (eventId && sessions.data.some((s) => s.external_event_id === eventId)) return eventId;
    return sessions.data[0].external_event_id;
  }, [sessions.data, eventId]);

  useEffect(() => {
    if (selectedEventId && selectedEventId !== eventId) {
      navigate(`/sessions/${selectedEventId}`, { replace: true });
    }
  }, [selectedEventId, eventId, navigate]);

  return (
    <div>
      <h1>Sessions</h1>
      {(athlete.isLoading || sessions.isLoading) && <p>Loading…</p>}
      {(athlete.isError || sessions.isError) && (
        <p role="alert">Could not load your sessions. Try reloading the page.</p>
      )}
      {sessions.data && sessions.data.length === 0 && (
        <p>No sessions yet. Report a transponder on the Import page to start syncing your training data.</p>
      )}

      {athlete.data && sessions.data && sessions.data.length > 0 && selectedEventId && (
        <Card>
          <Select
            className="sessions-page__selector"
            label="Session"
            value={selectedEventId}
            onChange={(e) => navigate(`/sessions/${e.target.value}`)}
          >
            {sessions.data.map((session) => (
              <option key={session.external_event_id} value={session.external_event_id}>
                {sessionLabel(session, sessions.data ?? [])}
              </option>
            ))}
          </Select>

          <SessionDetail athleteId={athlete.data.id} eventId={selectedEventId} />
        </Card>
      )}
    </div>
  );
}
