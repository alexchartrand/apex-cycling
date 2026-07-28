import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Button, Card, Select } from "../components/ui";
import { useMyAthlete } from "../features/athletes/useAthlete";
import { formatMs } from "../features/training/format";
import { TrackSchema } from "../features/training/TrackSchema";
import type { LapDetail, SessionSummary, TrackLoopSummary, TrackSessionDetail } from "../features/training/types";
import { useSessionDetail, useSessions, useTracks } from "../features/training/useTraining";
import "./SessionsPage.css";

const FLYING_200_VIEW_NAME = "200m";

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
      stroke={isSelected ? "var(--apex-ink)" : "none"}
      strokeWidth={isSelected ? 2 : 0}
    />
  );
}

function LapChart({ laps, selectedLapId }: { laps: LapDetail[]; selectedLapId: string | null }) {
  const data = laps
    .filter((lap) => lap.whole_lap_time_ms != null || flying200Ms(lap) != null)
    .map((lap, index) => ({
      lapId: lap.lap_id,
      label: lapLabel(lap, index),
      lapTimeMs: lap.whole_lap_time_ms,
      flying200Ms: flying200Ms(lap) ?? null,
    }));

  if (data.length === 0) return null;

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ left: 12, right: 12 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="label" />
        <YAxis
          yAxisId="left"
          domain={["dataMin - 200", "dataMax + 200"]}
          tickFormatter={formatChartSeconds}
          width={64}
        />
        <YAxis
          yAxisId="right"
          orientation="right"
          domain={["dataMin - 200", "dataMax + 200"]}
          tickFormatter={formatChartSeconds}
          width={64}
        />
        <Tooltip formatter={(value, name) => [formatChartSeconds(typeof value === "number" ? value : null), name]} />
        <Line
          yAxisId="left"
          type="monotone"
          dataKey="lapTimeMs"
          name="Whole lap"
          stroke="var(--accent)"
          dot={(props: any) => (
            <HighlightDot
              key={props.payload?.lapId ?? props.index}
              {...props}
              lapId={props.payload?.lapId}
              selectedLapId={selectedLapId}
              color="var(--accent)"
            />
          )}
        />
        <Line
          yAxisId="right"
          type="monotone"
          dataKey="flying200Ms"
          name="Flying 200"
          stroke="var(--apex-amber-deep)"
          dot={(props: any) => (
            <HighlightDot
              key={props.payload?.lapId ?? props.index}
              {...props}
              lapId={props.payload?.lapId}
              selectedLapId={selectedLapId}
              color="var(--apex-amber-deep)"
            />
          )}
        />
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
  const chartRef = useRef<HTMLDivElement>(null);

  const bestLapTime = useMemo(() => bestLap(track.laps, (lap) => lap.whole_lap_time_ms), [track.laps]);
  const bestFlying200 = useMemo(() => bestLap(track.laps, flying200Ms), [track.laps]);

  function selectLap(lapId: string) {
    setSelectedLapId(lapId);
    chartRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  return (
    <section>
      <div className="session-track__stats">
        <div className="session-track__stat">
          <span className="session-track__stat-label">Best lap time</span>
          <span className="session-track__stat-value">{formatMs(bestLapTime?.value)}</span>
          {bestLapTime && (
            <Button type="button" scale="sm" onClick={() => selectLap(bestLapTime.lap.lap_id)}>
              {lapLabel(bestLapTime.lap, bestLapTime.index)}
            </Button>
          )}
        </div>
        <div className="session-track__stat">
          <span className="session-track__stat-label">Best flying 200 time</span>
          <span className="session-track__stat-value">{formatMs(bestFlying200?.value)}</span>
          {bestFlying200 && (
            <Button type="button" scale="sm" onClick={() => selectLap(bestFlying200.lap.lap_id)}>
              {lapLabel(bestFlying200.lap, bestFlying200.index)}
            </Button>
          )}
        </div>
      </div>
      <div ref={chartRef} className="session-track__chart">
        <LapChart laps={track.laps} selectedLapId={selectedLapId} />
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
