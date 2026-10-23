import type { SessionDetail, SessionUpdate } from "../types";

export type Draft = { title: string; rpe: string; notes: string; tags: string[]; isRace: boolean };

export const draftOf = (session: SessionDetail): Draft => ({
  title: session.title_override ?? "",
  rpe: session.rpe == null ? "" : String(session.rpe),
  notes: session.notes ?? "",
  tags: session.tags,
  isRace: session.is_race,
});

/** The fields that differ from what's saved; blank text and "not rated" clear a field. */
export function changesFrom(session: SessionDetail, draft: Draft): SessionUpdate {
  const saved = draftOf(session);
  const changes: SessionUpdate = {};
  if (draft.title.trim() !== saved.title) changes.title_override = draft.title.trim() || null;
  if (draft.rpe !== saved.rpe) changes.rpe = draft.rpe === "" ? null : Number(draft.rpe);
  if (draft.notes.trim() !== saved.notes) changes.notes = draft.notes.trim() || null;
  if (draft.tags.join("\n") !== saved.tags.join("\n")) changes.tags = draft.tags;
  if (draft.isRace !== saved.isRace) changes.is_race = draft.isRace;
  return changes;
}
