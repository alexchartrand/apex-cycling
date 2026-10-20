import { flying200Ms, lapNumber } from "./sessionStats";
import type { LapDetail } from "./types";

export type SplitColumn = { loopId: string; name: string };

/**
 * The checkpoint columns of a session's lap table, in lap order. Checkpoint
 * order is fixed within a session, so the lap with the most checkpoints sets
 * it; a checkpoint only some other lap has (a rare re-configuration) is added
 * at the end. Hidden checkpoints (track settings) are left out.
 */
export function splitColumns(laps: LapDetail[], hiddenLoopIds: ReadonlySet<string>): SplitColumn[] {
  const fullest = laps.reduce<LapDetail | null>(
    (best, lap) => (best == null || lap.segments.length > best.segments.length ? lap : best),
    null,
  );
  const columns: SplitColumn[] = [];
  const seen = new Set<string>();
  const add = (lap: LapDetail) => {
    for (const segment of [...lap.segments].sort((a, b) => a.sequence_index - b.sequence_index)) {
      if (seen.has(segment.loop_id) || hiddenLoopIds.has(segment.loop_id)) continue;
      seen.add(segment.loop_id);
      columns.push({ loopId: segment.loop_id, name: segment.loop_name });
    }
  };
  if (fullest) add(fullest);
  laps.forEach(add);
  return columns;
}

/** This lap's own duration between the previous checkpoint and `loopId`; null if not captured. */
export function splitMs(lap: LapDetail, loopId: string): number | null {
  return lap.segments.find((segment) => segment.loop_id === loopId)?.time_ms ?? null;
}

export function lapSpeedKmh(lap: LapDetail, lapLengthM: number | null | undefined): number | null {
  const ms = lap.whole_lap_time_ms;
  return lapLengthM && ms ? (lapLengthM / (ms / 1000)) * 3.6 : null;
}

/** Which recorded channels any lap of the table has, so empty columns stay out. */
export function recordingColumns(laps: LapDetail[]): { power: boolean; heartRate: boolean; cadence: boolean } {
  return {
    power: laps.some((lap) => lap.avg_power_w != null),
    heartRate: laps.some((lap) => lap.avg_heart_rate != null),
    cadence: laps.some((lap) => lap.avg_cadence != null),
  };
}

function csvField(value: string | number | null): string {
  if (value == null) return "";
  const text = String(value);
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

const seconds = (ms: number | null) => (ms == null ? null : (ms / 1000).toFixed(3));
const rounded = (value: number | null | undefined) => (value == null ? null : Math.round(value));

/**
 * The lap table as CSV. Deliberately machine-readable whatever the UI
 * language: comma separated, "." decimals, seconds, ISO timestamps.
 */
export function lapsToCsv(laps: LapDetail[], columns: SplitColumn[], lapLengthM: number | null | undefined): string {
  const recorded = recordingColumns(laps);
  const header = [
    "lap",
    "start_time",
    "lap_time_s",
    "speed_kmh",
    "flying_200_s",
    ...(recorded.power ? ["avg_power_w"] : []),
    ...(recorded.heartRate ? ["avg_heart_rate_bpm"] : []),
    ...(recorded.cadence ? ["avg_cadence_rpm"] : []),
    ...columns.map((c) => `${c.name}_s`),
    "excluded",
    "label",
  ];
  const rows = laps.map((lap, index) => {
    const speed = lapSpeedKmh(lap, lapLengthM);
    return [
      lapNumber(lap, index),
      lap.start_time,
      seconds(lap.whole_lap_time_ms),
      speed == null ? null : speed.toFixed(2),
      seconds(flying200Ms(lap)),
      ...(recorded.power ? [rounded(lap.avg_power_w)] : []),
      ...(recorded.heartRate ? [rounded(lap.avg_heart_rate)] : []),
      ...(recorded.cadence ? [rounded(lap.avg_cadence)] : []),
      ...columns.map((c) => seconds(splitMs(lap, c.loopId))),
      lap.excluded ? "yes" : "no",
      lap.label,
    ];
  });
  return [header, ...rows].map((row) => row.map(csvField).join(",")).join("\r\n") + "\r\n";
}
