import type { Formatters } from "../../i18n/format";
import { parseTimeInput, timeToInput } from "./timeInput";
import { EVENT_START_TYPES, STANDARD_EVENT_KEYS, type ManualResult, type ManualResultPayload, type StandardEventKey } from "./types";

export type ManualForm = {
  eventKey: StandardEventKey;
  startType: "standing" | "flying";
  time: string;
  date: string;
  placeKind: "track" | "venue";
  trackId: string;
  venue: string;
  competition: boolean;
  notes: string;
};

export type ManualFormErrors = { time?: true; place?: true };

/** A new result: the first standing-start distance, today, at the first track known (or a venue if none). */
export function emptyManualForm(today: string, firstTrackId: string | null): ManualForm {
  return {
    eventKey: "500m",
    startType: "standing",
    time: "",
    date: today,
    placeKind: firstTrackId ? "track" : "venue",
    trackId: firstTrackId ?? "",
    venue: "",
    competition: false,
    notes: "",
  };
}

export function manualFormFrom(result: ManualResult, fmt: Pick<Formatters, "seconds" | "lapTime">): ManualForm {
  return {
    eventKey: (STANDARD_EVENT_KEYS as readonly string[]).includes(result.event_key) ? (result.event_key as StandardEventKey) : "500m",
    startType: result.start_type,
    time: timeToInput(result.time_ms, fmt),
    date: result.achieved_on,
    placeKind: result.track_id ? "track" : "venue",
    trackId: result.track_id ?? "",
    venue: result.venue ?? "",
    competition: result.is_competition,
    notes: result.notes ?? "",
  };
}

/** Switching event keeps the start type when the new event has it, else falls back to its first. */
export function withEvent(form: ManualForm, eventKey: StandardEventKey): ManualForm {
  const allowed = EVENT_START_TYPES[eventKey];
  return { ...form, eventKey, startType: allowed.includes(form.startType) ? form.startType : allowed[0] };
}

export function manualFormErrors(form: ManualForm): ManualFormErrors {
  const errors: ManualFormErrors = {};
  if (parseTimeInput(form.time) == null) errors.time = true;
  if (form.placeKind === "track" ? form.trackId === "" : form.venue.trim() === "") errors.place = true;
  return errors;
}

/** The request body, or null while the form has errors. */
export function manualPayload(form: ManualForm): ManualResultPayload | null {
  const time_ms = parseTimeInput(form.time);
  if (time_ms == null || Object.keys(manualFormErrors(form)).length > 0 || !form.date) return null;
  return {
    event_key: form.eventKey,
    start_type: form.startType,
    time_ms,
    achieved_on: form.date,
    track_id: form.placeKind === "track" ? form.trackId : null,
    venue: form.placeKind === "venue" ? form.venue.trim() : null,
    is_competition: form.competition,
    notes: form.notes.trim() || null,
  };
}
