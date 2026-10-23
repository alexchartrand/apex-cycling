import type { Bike } from "../equipment/types";
import type { Effort, LinkedActivity, TrackSessionDetail } from "../training/types";

/** An effort's span on a recording's own clock (seconds since its first sample). */
export interface EffortBand {
  fromS: number;
  toS: number;
  /** The effort's number in the session (as on the Efforts tab). */
  index: number;
  label: string | null;
}

/** What the session page lays over a linked recording's chart. */
export interface SessionOverlay {
  /** Epoch ms (sqorz time) of the recording's x = 0. */
  clockStartMs: number;
  bands: EffortBand[];
  laps: LapSpeed[];
  gearing: Gearing;
}

/**
 * The gear ridden, as metres of travel per crank turn: the session's for the
 * whole recording, an effort's own where it set one. Null where none is known.
 */
export interface Gearing {
  sessionDevelopmentM: number | null;
  efforts: { fromS: number; toS: number; developmentM: number }[];
}

/** The gearing of a session on a recording's clock, from its gear choices and the athlete's bikes. */
export function sessionGearing(
  sessionGearId: string | null | undefined,
  efforts: Effort[],
  bikes: Bike[],
  recording: Pick<LinkedActivity, "start_time" | "clock_offset_s" | "elapsed_s">,
): Gearing {
  const developments = new Map(bikes.flatMap((bike) => bike.gears.map((gear) => [gear.id, gear.development_m] as const)));
  const bands = new Map(effortBands(efforts, recording).map((band) => [band.index, band]));
  const own: Gearing["efforts"] = [];
  for (const effort of efforts) {
    const band = bands.get(effort.index);
    const developmentM = effort.gear_setup_id ? developments.get(effort.gear_setup_id) : undefined;
    if (band && developmentM) own.push({ fromS: band.fromS, toS: band.toS, developmentM });
  }
  return { sessionDevelopmentM: (sessionGearId && developments.get(sessionGearId)) || null, efforts: own };
}

/** The development in force at a moment of the recording (seconds on its clock). */
export function developmentAt(gearing: Gearing, x: number): number | null {
  return gearing.efforts.find((span) => span.fromS <= x && x <= span.toS)?.developmentM ?? gearing.sessionDevelopmentM;
}

/** A lap on a recording's clock with sqorz's speed over it. */
export interface LapSpeed {
  fromS: number;
  toS: number;
  kmh: number;
}

/**
 * Seconds to add to a sqorz timestamp (epoch ms) to land on the recording's
 * clock. `clock_offset_s` is what is *added to device time* to get sqorz time,
 * so it is subtracted here (the backend's `fusion_service.Recording` does the same).
 */
function toRecording(recording: Pick<LinkedActivity, "start_time" | "clock_offset_s">): (epochMs: number) => number {
  const origin = new Date(recording.start_time).getTime() / 1000 + recording.clock_offset_s;
  return (epochMs) => epochMs / 1000 - origin;
}

/** Epoch ms (sqorz time) of the recording's x = 0, to label its axis with the session's clock. */
export function recordingClockStart(recording: Pick<LinkedActivity, "start_time" | "clock_offset_s">): number {
  return new Date(recording.start_time).getTime() + recording.clock_offset_s * 1000;
}

/** The session's efforts that fall (at least partly) inside the recording. */
export function effortBands(
  efforts: Effort[],
  recording: Pick<LinkedActivity, "start_time" | "clock_offset_s" | "elapsed_s">,
): EffortBand[] {
  const at = toRecording(recording);
  const bands: EffortBand[] = [];
  for (const effort of efforts) {
    const durationMs = effort.lap_times_ms.reduce<number>((sum, ms) => sum + (ms ?? 0), 0);
    if (durationMs <= 0) continue;
    const fromS = at(new Date(effort.start_time).getTime());
    const toS = fromS + durationMs / 1000;
    if (toS <= 0 || fromS >= recording.elapsed_s) continue;
    bands.push({ fromS, toS, index: effort.index, label: effort.label });
  }
  return bands;
}

/**
 * Sqorz's speed per lap (track length ÷ lap time) on the recording's clock,
 * in time order. Laps of tracks without a length, unfinished and excluded
 * laps are left out.
 */
export function lapSpeeds(
  tracks: TrackSessionDetail[],
  trackLengths: Map<string, number>,
  recording: Pick<LinkedActivity, "start_time" | "clock_offset_s" | "elapsed_s">,
): LapSpeed[] {
  const at = toRecording(recording);
  const laps: LapSpeed[] = [];
  for (const track of tracks) {
    const length = trackLengths.get(track.track_id);
    if (!length) continue;
    for (const lap of track.laps) {
      if (lap.excluded || !lap.whole_lap_time_ms) continue;
      const fromS = at(new Date(lap.start_time).getTime());
      const toS = fromS + lap.whole_lap_time_ms / 1000;
      if (toS <= 0 || fromS >= recording.elapsed_s) continue;
      laps.push({ fromS, toS, kmh: (length / (lap.whole_lap_time_ms / 1000)) * 3.6 });
    }
  }
  return laps.sort((a, b) => a.fromS - b.fromS);
}
