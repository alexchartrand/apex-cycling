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

/** Mean of a channel over the rows inside [from, to] (x units); null with no readings. */
export function windowAverage(rows: StreamRow[], channel: Channel, from: number, to: number): number | null {
  const values = rows.filter((r) => r.x >= from && r.x <= to).map((r) => r[channel]).filter((v): v is number => v != null);
  return values.length === 0 ? null : values.reduce((a, b) => a + b, 0) / values.length;
}
