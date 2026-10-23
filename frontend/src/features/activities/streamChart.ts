import { developmentAt, type Gearing, type LapSpeed, type SessionOverlay } from "./sessionOverlay";
import type { ActivityStreams } from "./types";

export type XAxisMode = "time" | "distance";
export type Channel = "power" | "heartRate" | "cadence" | "speed" | "altitude";

export interface StreamRow {
  /** Seconds, or kilometres when the x axis is distance. */
  x: number;
  power: number | null;
  heartRate: number | null;
  cadence: number | null;
  /** km/h */
  speed: number | null;
  altitude: number | null;
  /** km/h sqorz measured over the lap this sample falls in (session page only). */
  sqorzSpeed?: number | null;
  /** rpm the gear ridden implies at the recorded speed (session page only; a fixed gear never coasts). */
  estCadence?: number | null;
}

/** Channels the recording carries, in the order they are offered. */
export function availableChannels(streams: ActivityStreams): Channel[] {
  const channels: Channel[] = [];
  if (streams.power_w) channels.push("power");
  if (streams.heart_rate) channels.push("heartRate");
  if (streams.cadence) channels.push("cadence");
  if (streams.speed_mps) channels.push("speed");
  if (streams.altitude_m) channels.push("altitude");
  return channels;
}

/** Whether distance can be the x axis (it must grow, not just exist). */
export function canUseDistance(streams: ActivityStreams): boolean {
  const distance = streams.distance_m?.filter((d): d is number => d != null) ?? [];
  return distance.length > 1 && distance[distance.length - 1] > distance[0];
}

export function toRows(streams: ActivityStreams, mode: XAxisMode): StreamRow[] {
  const rows: StreamRow[] = [];
  const useDistance = mode === "distance" && canUseDistance(streams);
  for (let i = 0; i < streams.point_count; i++) {
    const rawX = useDistance ? streams.distance_m?.[i] : streams.time_s[i];
    if (rawX == null) continue;
    const speed = streams.speed_mps?.[i];
    rows.push({
      x: useDistance ? rawX / 1000 : rawX,
      power: streams.power_w?.[i] ?? null,
      heartRate: streams.heart_rate?.[i] ?? null,
      cadence: streams.cadence?.[i] ?? null,
      speed: speed == null ? null : speed * 3.6,
      altitude: streams.altitude_m?.[i] ?? null,
    });
  }
  return rows;
}

/** Time-axis rows with sqorz's speed of the lap each sample falls in (`laps` in time order, x in seconds). */
export function withLapSpeed(rows: StreamRow[], laps: LapSpeed[]): StreamRow[] {
  let i = 0;
  return rows.map((row) => {
    while (i < laps.length && laps[i].toS < row.x) i++;
    const lap = laps[i];
    return { ...row, sqorzSpeed: lap && lap.fromS <= row.x ? lap.kmh : null };
  });
}

/** Time-axis rows with the cadence the gear implies at the recorded speed (x in seconds). */
export function withEstimatedCadence(rows: StreamRow[], gearing: Gearing): StreamRow[] {
  return rows.map((row) => {
    const developmentM = developmentAt(gearing, row.x);
    return { ...row, estCadence: developmentM && row.speed != null ? (row.speed / 3.6 / developmentM) * 60 : null };
  });
}

/**
 * The recording's channels plus those only the session overlay fills: speed
 * for sqorz's lap speed (a power meter alone records none), cadence for the
 * one estimated from the gear (no cadence sensor).
 */
export function withOverlayChannels(channels: Channel[], extra: Channel[]): Channel[] {
  const order: Channel[] = ["power", "heartRate", "cadence", "speed", "altitude"];
  return order.filter((channel) => channels.includes(channel) || extra.includes(channel));
}

/**
 * Row indexes framing the session on the recording (its efforts and laps, a
 * margin either side), for the chart to open on; null when that is the whole
 * recording anyway.
 */
export function spanIndexes(rows: StreamRow[], overlay: Pick<SessionOverlay, "bands" | "laps">, marginS = 120): [number, number] | null {
  const spans = [...overlay.bands, ...overlay.laps];
  if (spans.length === 0 || rows.length < 2) return null;
  const from = Math.min(...spans.map((s) => s.fromS)) - marginS;
  const to = Math.max(...spans.map((s) => s.toS)) + marginS;
  const first = Math.max(rows.findIndex((r) => r.x >= from), 0);
  const after = rows.findIndex((r) => r.x > to);
  const last = after === -1 ? rows.length - 1 : Math.max(after - 1, first);
  return first === 0 && last === rows.length - 1 ? null : [first, last];
}

/** Mean of a channel over the rows inside [from, to] (x units); null with no readings. */
export function windowAverage(rows: StreamRow[], channel: Channel | "sqorzSpeed" | "estCadence", from: number, to: number): number | null {
  const values = rows.filter((r) => r.x >= from && r.x <= to).map((r) => r[channel]).filter((v): v is number => v != null);
  return values.length === 0 ? null : values.reduce((a, b) => a + b, 0) / values.length;
}
