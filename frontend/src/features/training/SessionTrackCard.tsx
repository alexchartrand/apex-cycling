import { useMemo, useRef, useState } from "react";
import { Flag, ListOrdered, Route, SlidersHorizontal, Timer } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button, Card, IconButton, Select, StatTile, Tooltip } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { LapChart, type LapChartMetric } from "./LapChart";
import { bestLap, DEFAULT_LAP_DISTANCE_M, flying200Ms, lapNumber, type BestLap } from "./sessionStats";
import { VelodromeDiagram } from "./VelodromeDiagram";
import { TrackSettingsDialog } from "./TrackSettingsDialog";
import type { TrackSessionDetail, TrackSummary } from "./types";
import "./SessionTrackCard.css";

const METRICS: LapChartMetric[] = ["lapTime", "flying200", "none"];

export function SessionTrackCard({ track, meta }: { track: TrackSessionDetail; meta: TrackSummary | undefined }) {
  const { t } = useTranslation("training");
  const fmt = useFormat();
  const [selectedLapId, setSelectedLapId] = useState<string | null>(null);
  const [leftMetric, setLeftMetric] = useState<LapChartMetric>("lapTime");
  const [rightMetric, setRightMetric] = useState<LapChartMetric>("flying200");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const chartRef = useRef<HTMLDivElement>(null);
  const lengthM = meta?.length_m;

  const bestLapTime = useMemo(() => bestLap(track.laps, (lap) => lap.whole_lap_time_ms), [track.laps]);
  const bestFlying200 = useMemo(() => bestLap(track.laps, flying200Ms), [track.laps]);

  function showLap(best: BestLap) {
    setSelectedLapId(best.lap.lap_id);
    chartRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function jumpButton(best: BestLap | null) {
    if (!best) return undefined;
    const label = t("session.lapNumber", { n: lapNumber(best.lap, best.index) });
    return (
      <Button size="sm" variant="ghost" className="track-card__jump" aria-label={t("session.showOnChart", { lap: label })} onClick={() => showLap(best)}>
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
      <div className="track-card__stats">
        <StatTile label={t("session.laps")} icon={<ListOrdered aria-hidden />} value={track.laps.length} />
        <StatTile
          label={t("session.distance")}
          icon={<Route aria-hidden />}
          value={fmt.distance(track.laps.length * (lengthM ?? DEFAULT_LAP_DISTANCE_M))}
        />
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
      </div>

      <div className="track-card__controls">
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
        <LapChart laps={track.laps} selectedLapId={selectedLapId} leftMetric={leftMetric} rightMetric={rightMetric} />
      </div>

      <VelodromeDiagram loops={meta?.loops ?? []} lengthM={lengthM} />
      {meta?.can_edit && <TrackSettingsDialog track={meta} open={settingsOpen} onOpenChange={setSettingsOpen} />}
    </Card>
  );
}
