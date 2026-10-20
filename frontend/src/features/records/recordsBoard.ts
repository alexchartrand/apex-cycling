import { EVENT_START_TYPES, STANDARD_EVENT_KEYS, type RecordEntry, type RecordSelection, type StandardEventKey } from "./types";

export type PlaceGroup = { key: string; place: string; track_id: string | null; entries: RecordEntry[] };

/** Board entries grouped by place (a track, or a manual venue), keeping the board's order. */
export function groupByPlace(entries: RecordEntry[]): PlaceGroup[] {
  const groups = new Map<string, PlaceGroup>();
  for (const entry of entries) {
    const key = entry.track_id ?? `venue:${entry.place.trim().toLowerCase()}`;
    const group = groups.get(key) ?? { key, place: entry.place, track_id: entry.track_id, entries: [] };
    group.entries.push(entry);
    groups.set(key, group);
  }
  return [...groups.values()];
}

/** Each improvement's gain over the previous record in a history, in ms (negative = faster); null for the first. */
export function improvements(history: RecordEntry[]): (number | null)[] {
  return history.map((entry, i) => (i === 0 ? null : entry.time_ms - history[i - 1].time_ms));
}

export const isEventKey = (key: string): key is StandardEventKey => (STANDARD_EVENT_KEYS as readonly string[]).includes(key);

/** A stable id for a board line: place, event and start type. */
export const entryId = (entry: RecordEntry) => `${entry.track_id ?? entry.place}|${entry.event_key}|${entry.start_type}`;

/** What to ask the history endpoint for; null if the entry isn't a standard event/start combination. */
export function selectionOf(entry: RecordEntry): RecordSelection | null {
  if (!isEventKey(entry.event_key)) return null;
  const start = entry.start_type;
  if (start !== "standing" && start !== "flying") return null;
  if (!EVENT_START_TYPES[entry.event_key].includes(start)) return null;
  return { track_id: entry.track_id, place: entry.place, event_key: entry.event_key, start_type: start };
}
