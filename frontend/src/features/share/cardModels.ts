import type { RecordEntry } from "../records/types";
import type { Effort, LapDetail } from "../training/types";
import { eventLapCount, recordTimeText, windowSplits, type CardFormat, type ShareCardModel } from "./shareCard";

/** Texts the caller translates; the builders only add numbers and dates. */
export interface CardTexts {
  brand: string;
  eyebrow: string;
  title: string;
  splitsCaption: string;
  /** What the delta is against ("vs previous best"), or "first time under 48.000 s". */
  deltaNote: string | null;
}

export interface RecordCardInput {
  record: RecordEntry;
  /** The session's laps on the record's track, for the splits. */
  laps: LapDetail[];
  trackLengthM: number | null;
  /** The best before this one, when the session's insights know it. */
  previousMs: number | null;
}

export function recordCardModel(input: RecordCardInput, texts: CardTexts, fmt: CardFormat): ShareCardModel {
  const { record, laps, trackLengthM, previousMs } = input;
  return {
    brand: texts.brand,
    eyebrow: texts.eyebrow,
    title: texts.title,
    time: recordTimeText(record.time_ms, fmt),
    delta: previousMs != null && previousMs > record.time_ms ? `${fmt.deltaSeconds(record.time_ms - previousMs)} s` : null,
    deltaNote: texts.deltaNote,
    place: record.place,
    date: fmt.date(record.achieved_on, "long"),
    splitsCaption: texts.splitsCaption,
    splits: windowSplits(laps, record.lap_id, eventLapCount(record.event_key, trackLengthM)),
    trackLengthM,
  };
}

export interface EffortCardInput {
  effort: Effort;
  date: string;
  trackLengthM: number | null;
}

export function effortCardModel(input: EffortCardInput, texts: CardTexts, fmt: CardFormat): ShareCardModel {
  const { effort } = input;
  const splits = effort.lap_times_ms.flatMap((ms, index) => (ms == null ? [] : [{ label: String(index + 1), ms }]));
  return {
    brand: texts.brand,
    eyebrow: texts.eyebrow,
    title: texts.title,
    time: effort.total_time_ms != null ? recordTimeText(effort.total_time_ms, fmt) : "—",
    delta: null,
    deltaNote: texts.deltaNote,
    place: effort.track_name,
    date: fmt.date(input.date, "long"),
    splitsCaption: texts.splitsCaption,
    splits,
    trackLengthM: input.trackLengthM,
  };
}
