import { useMemo, useRef, useState } from "react";
import { Flag, Gauge, ListOrdered, Route, SlidersHorizontal, Timer, Trophy, Hourglass } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Card, IconButton, Select, StatTile, Tooltip } from "../../../components/ui";
import { useFormat } from "../../../i18n/useFormat";
import type { RecordEntry } from "../../records/types";
import { LapChart, type LapChartMetric } from "../LapChart";
import {
  bestLap,
  DEFAULT_LAP_DISTANCE_M,
  distanceRiddenM,
  flying200Ms,
  lapNumber,
  ridingTimeMs,
  topSpeedKmh,
  type BestLap,
} from "../sessionStats";
import { TrackSettingsDialog } from "../TrackSettingsDialog";
import type { TrackSessionDetail, TrackSummary } from "../types";
import "./TrackOverview.css";

const METRICS: LapChartMetric[] = ["lapTime", "flying200", "none"];

/** One track of a session: headline numbers, the records it set, and the lap chart. */
export function TrackOverview({
  track,
  meta,
  records,
}: {
  track: TrackSessionDetail;
  meta: TrackSummary | undefined;
  /** Records whose performance happened in this session, on this track. */
  records: RecordEntry[];
}) {
  const { t } = useTranslation("training");
  const { t: tr } = useTranslation("records");
  const fmt = useFormat();
  const [selectedLapId, setSelectedLapId] = useState<string | null>(null);
  const [leftMetric, setLeftMetric] = useState<LapChartMetric>("lapTime");
  const [rightMetric, setRightMetric] = useState<LapChartMetric>("flying200");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const chartRef = useRef<HTMLDivElement>(null);

  const lengthKnown = meta?.length_m != null;
  const lapLengthM = meta?.length_m ?? DEFAULT_LAP_DISTANCE_M;
  const bestLapTime = useMemo(() => bestLap(track.laps, (lap) => lap.whole_lap_time_ms), [track.laps]);
  const bestFlying200 = useMemo(() => bestLap(track.laps, flying200Ms), [track.laps]);
  const topSpeed = useMemo(() => topSpeedKmh(track.laps, lapLengthM), [track.laps, lapLengthM]);
  const chartLaps = useMemo(() => track.laps.filter((lap) => !lap.excluded), [track.laps]);
  const hasExcluded = chartLaps.length < track.laps.length;

  function showLap(best: BestLap) {
    setSelectedLapId(best.lap.lap_id);
    chartRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function jumpButton(best: BestLap | null) {
    if (!best) return undefined;
    const label = t("session.lapNumber", { n: lapNumber(best.lap, best.index) });
    return (
      <Button size="sm" variant="ghost" className="track-overview__jump" aria-label={t("session.showOnChart", { lap: label })} onClick={() => showLap(best)}>
        {label}
      </Button>
    );
  }

  return (
    <Card
      eyebrow={t("session.track")}
      title={track.track_name}
      actions={
        meta?.can_edit ? (
          <Tooltip content={t("trackSettings.open")}>
            <IconButton aria-label={t("trackSettings.open")} variant="ghost" onClick={() => setSettingsOpen(true)}>
              <SlidersHorizontal aria-hidden />
            </IconButton>
          </Tooltip>
        ) : undefined
      }
    >
      <div className="track-overview__stats">
        <StatTile label={t("session.laps")} icon={<ListOrdered aria-hidden />} value={track.laps.length} />
        <StatTile label={t("session.distance")} icon={<Route aria-hidden />} value={fmt.distance(distanceRiddenM(track.laps, lapLengthM))} />
        <StatTile label={t("session.ridingTime")} icon={<Hourglass aria-hidden />} value={fmt.duration(ridingTimeMs(track.laps) / 1000)} />
        <StatTile
          label={t("session.bestLap")}
          icon={<Timer aria-hidden />}
          tone="accent"
          value={fmt.lapTime(bestLapTime?.value)}
          hint={jumpButton(bestLapTime)}
        />
        <StatTile
          label={t("session.bestF200")}
          icon={<Flag aria-hidden />}
          tone="highlight"
          value={bestFlying200 ? fmt.seconds(bestFlying200.value) : "—"}
          unit={bestFlying200 ? "s" : undefined}
          hint={jumpButton(bestFlying200)}
        />
        <StatTile
          label={t("session.topSpeed")}
          icon={<Gauge aria-hidden />}
          value={topSpeed != null ? fmt.number(topSpeed, 1, 1) : "—"}
          unit={topSpeed != null ? "km/h" : undefined}
        />
      </div>
      {!lengthKnown && <p className="track-overview__note">{t("session.assumedLength", { length: fmt.distance(DEFAULT_LAP_DISTANCE_M) })}</p>}

      <section className="track-overview__records" aria-label={t("session.recordsTitle")}>
        <h4 className="track-overview__subtitle">{t("session.recordsTitle")}</h4>
        {records.length === 0 ? (
          <p className="track-overview__note">{t("session.recordsNone")}</p>
        ) : (
          <ul className="track-overview__badges">
            {records.map((record) => (
              <li key={`${record.event_key}-${record.start_type}`}>
                <Badge tone="marker" icon={<Trophy aria-hidden />}>
                  {tr("badge")} · {tr(`events.${record.event_key as "f200"}`)} · {tr(`startTypes.${record.start_type}`)} ·{" "}
                  {record.time_ms < 60_000 ? `${fmt.seconds(record.time_ms)} s` : fmt.lapTime(record.time_ms)}
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="track-overview__controls">
        <Select scale="sm" label={t("session.leftAxis")} value={leftMetric} onChange={(e) => setLeftMetric(e.target.value as LapChartMetric)}>
          {METRICS.map((metric) => (
            <option key={metric} value={metric}>
              {t(`session.metrics.${metric}`)}
            </option>
          ))}
        </Select>
        <Select scale="sm" label={t("session.rightAxis")} value={rightMetric} onChange={(e) => setRightMetric(e.target.value as LapChartMetric)}>
          {METRICS.map((metric) => (
            <option key={metric} value={metric}>
              {t(`session.metrics.${metric}`)}
            </option>
          ))}
        </Select>
      </div>

      <div ref={chartRef}>
        <LapChart laps={chartLaps} selectedLapId={selectedLapId} leftMetric={leftMetric} rightMetric={rightMetric} />
        {hasExcluded && <p className="track-overview__note">{t("session.excludedChartNote")}</p>}
      </div>

      {meta?.can_edit && <TrackSettingsDialog track={meta} open={settingsOpen} onOpenChange={setSettingsOpen} />}
    </Card>
  );
}
