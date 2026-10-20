import { describe, expect, it } from "vitest";
import { createFormatters } from "../../i18n/format";
import { emptyManualForm, manualFormErrors, manualFormFrom, manualPayload, withEvent } from "./manualForm";
import type { ManualResult } from "./types";

describe("manual result form", () => {
  const blank = emptyManualForm("2026-10-19", "t1");

  it("starts on a track when one is known, otherwise on a venue", () => {
    expect(blank).toMatchObject({ placeKind: "track", trackId: "t1", eventKey: "500m", startType: "standing", date: "2026-10-19" });
    expect(emptyManualForm("2026-10-19", null)).toMatchObject({ placeKind: "venue", trackId: "" });
  });

  it("keeps the start type across events that have it, and falls back for those that don't", () => {
    expect(withEvent({ ...blank, startType: "flying" }, "1km").startType).toBe("flying");
    expect(withEvent(blank, "f200")).toMatchObject({ eventKey: "f200", startType: "flying" }); // a 200 is only flying
    expect(withEvent(blank, "lap").startType).toBe("flying");
  });

  it("needs a plausible time and a place", () => {
    expect(manualFormErrors(blank)).toEqual({ time: true });
    expect(manualFormErrors({ ...blank, time: "36.5" })).toEqual({});
    expect(manualFormErrors({ ...blank, time: "36.5", placeKind: "venue", venue: "  " })).toEqual({ place: true });
    expect(manualFormErrors({ ...blank, time: "nope", trackId: "" })).toEqual({ time: true, place: true });
  });

  it("builds the payload: time in ms, one of track/venue, blank notes dropped", () => {
    expect(manualPayload(blank)).toBeNull();
    expect(manualPayload({ ...blank, time: "1:12,345", competition: true, notes: "  " })).toEqual({
      event_key: "500m",
      start_type: "standing",
      time_ms: 72_345,
      achieved_on: "2026-10-19",
      track_id: "t1",
      venue: null,
      is_competition: true,
      notes: null,
    });
    expect(manualPayload({ ...blank, time: "36.5", placeKind: "venue", venue: " Mont-Royal ", trackId: "t1", notes: "Provincials" })).toMatchObject({
      track_id: null,
      venue: "Mont-Royal",
      notes: "Provincials",
    });
  });

  it("needs a date", () => {
    expect(manualPayload({ ...blank, time: "36.5", date: "" })).toBeNull();
  });

  it("loads a saved result back into the form, time in the UI language", () => {
    const result: ManualResult = {
      id: "m1",
      event_key: "1km",
      start_type: "flying",
      time_ms: 72_345,
      achieved_on: "2026-08-01",
      track_id: null,
      venue: "Mont-Royal",
      place: "Mont-Royal",
      is_competition: true,
      notes: null,
    };
    expect(manualFormFrom(result, createFormatters("fr"))).toEqual({
      eventKey: "1km",
      startType: "flying",
      time: "1:12,345",
      date: "2026-08-01",
      placeKind: "venue",
      trackId: "",
      venue: "Mont-Royal",
      competition: true,
      notes: "",
    });
  });
});
