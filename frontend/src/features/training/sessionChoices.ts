import type { SessionSummary } from "./types";

/** The selected sessions that aren't among the loaded ones. */
export function missingChoices(loaded: SessionSummary[], selected: string[]): string[] {
  const known = new Set(loaded.map((s) => s.external_event_id));
  return [...new Set(selected.filter((id) => id !== "" && !known.has(id)))];
}

/** Loaded pages plus extra sessions, without repeats, newest first (as the server orders them). */
export function mergeChoices(loaded: SessionSummary[], extra: SessionSummary[]): SessionSummary[] {
  const seen = new Set<string>();
  const merged: SessionSummary[] = [];
  for (const session of [...loaded, ...extra]) {
    if (seen.has(session.external_event_id)) continue;
    seen.add(session.external_event_id);
    merged.push(session);
  }
  if (extra.length === 0) return merged;
  return merged.sort((a, b) =>
    a.event_date === b.event_date ? (b.first_lap_at ?? "").localeCompare(a.first_lap_at ?? "") : a.event_date < b.event_date ? 1 : -1,
  );
}
