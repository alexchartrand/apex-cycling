import { Link, useParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useMyAthlete } from "../features/athletes/useAthlete";
import { formatMs } from "../features/training/format";
import type { LapDetail } from "../features/training/types";
import { useSessionDetail } from "../features/training/useTraining";

function LapChart({ laps }: { laps: LapDetail[] }) {
  const data = laps
    .filter((lap) => lap.whole_lap_time_ms != null)
    .map((lap, index) => ({
      label: lap.start_number != null ? `#${lap.start_number}` : `Lap ${index + 1}`,
      time_ms: lap.whole_lap_time_ms as number,
    }));

  if (data.length === 0) return null;

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ left: 12 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="label" />
        <YAxis tickFormatter={formatMs} width={90} />
        <Tooltip formatter={(value) => formatMs(typeof value === "number" ? value : null)} />
        <Bar dataKey="time_ms" fill="var(--accent)" />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function SessionDetailPage() {
  const { eventId = "" } = useParams();
  const athlete = useMyAthlete();
  const detail = useSessionDetail(athlete.data?.id ?? "", eventId);

  return (
    <div>
      <p>
        <Link to="/sessions">← Sessions</Link>
      </p>
      {detail.isLoading && <p>Loading…</p>}
      {detail.isError && <p role="alert">Could not load this session.</p>}
      {detail.data && (
        <>
          <h1>{detail.data.event_name}</h1>
          <p>{detail.data.event_date}</p>
          {detail.data.tracks.map((track) => (
            <section key={track.track_id}>
              <h2>{track.track_name}</h2>
              <LapChart laps={track.laps} />
              <table>
                <thead>
                  <tr>
                    <th>Lap</th>
                    <th>Whole lap</th>
                    {track.laps[0]?.views.map((view) => <th key={view.track_view_id}>{view.name}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {track.laps.map((lap) => (
                    <tr key={lap.lap_id}>
                      <td>{lap.start_number != null ? `#${lap.start_number}` : "—"}</td>
                      <td>{formatMs(lap.whole_lap_time_ms)}</td>
                      {lap.views.map((view) => <td key={view.track_view_id}>{formatMs(view.time_ms)}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ))}
        </>
      )}
    </div>
  );
}
