import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Brush, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useMyAthlete } from "../features/athletes/useAthlete";
import { formatMs } from "../features/training/format";
import type { ProgressionParams } from "../features/training/types";
import { useProgression, useTracks } from "../features/training/useTraining";

const VIEW_PREFIX = "view:";

export function ProgressionPage() {
  const athlete = useMyAthlete();
  const athleteId = athlete.data?.id ?? "";
  const tracks = useTracks(athleteId);

  const [trackId, setTrackId] = useState<string>("");
  const [metricKey, setMetricKey] = useState<string>("lap_time");
  const [distanceM, setDistanceM] = useState<string>("");
  const [fromDate, setFromDate] = useState<string>("");
  const [toDate, setToDate] = useState<string>("");

  const selectedTrack = tracks.data?.find((t) => t.id === trackId);

  const params: ProgressionParams | null = useMemo(() => {
    if (!trackId) return null;
    const base = { from: fromDate || undefined, to: toDate || undefined };
    if (metricKey === "lap_time") {
      return { ...base, metric: "lap_time", track_id: trackId };
    }
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

  const chartData = (progression.data ?? []).map((point) => ({
    event_date: point.event_date,
    time_ms: point.time_ms,
    achieved_distance_m: point.achieved_distance_m,
  }));

  return (
    <div>
      <p>
        <Link to="/">← Dashboard</Link>
      </p>
      <h1>Progression</h1>

      {tracks.isLoading && <p>Loading tracks…</p>}
      {tracks.isError && <p role="alert">Could not load tracks. Try reloading the page.</p>}
      {tracks.data && tracks.data.length === 0 && (
        <p>No tracks yet. Report a transponder on the dashboard to start syncing your training data.</p>
      )}

      <form onSubmit={(e) => e.preventDefault()}>
        <label>
          Track
          <select
            value={trackId}
            onChange={(e) => {
              setTrackId(e.target.value);
              setMetricKey("lap_time");
            }}
          >
            <option value="">Select a track…</option>
            {tracks.data?.map((track) => (
              <option key={track.id} value={track.id}>
                {track.name}
              </option>
            ))}
          </select>
        </label>

        {trackId && (
          <label>
            Metric
            <select value={metricKey} onChange={(e) => setMetricKey(e.target.value)}>
              <option value="lap_time">Whole lap</option>
              <option value="custom_distance">Custom distance</option>
              {selectedTrack?.views.map((view) => (
                <option key={view.id} value={`${VIEW_PREFIX}${view.id}`}>
                  {view.name}
                </option>
              ))}
            </select>
          </label>
        )}

        {metricKey === "custom_distance" && (
          <label>
            Distance (m)
            <input
              type="number"
              min="1"
              value={distanceM}
              onChange={(e) => setDistanceM(e.target.value)}
              placeholder="e.g. 150"
            />
          </label>
        )}

        <label>
          From
          <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
        </label>
        <label>
          To
          <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
        </label>
      </form>

      {params && progression.isLoading && <p>Loading…</p>}
      {params && progression.isError && <p role="alert">Could not load progression data. Try again.</p>}
      {params && progression.data && progression.data.length === 0 && <p>No data for this selection yet.</p>}
      {chartData.length > 0 && (
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={chartData} margin={{ left: 12 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="event_date" />
            <YAxis tickFormatter={formatMs} width={90} />
            <Tooltip formatter={(value) => (typeof value === "number" ? formatMs(value) : String(value ?? ""))} />
            <Line type="monotone" dataKey="time_ms" stroke="var(--accent)" dot />
            <Brush dataKey="event_date" height={24} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
