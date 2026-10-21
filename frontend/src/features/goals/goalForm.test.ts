import { describe, expect, it } from "vitest";
import { dueState, emptyGoalForm, goalCreatePayload, goalFormErrors, goalUpdatePayload, predictedGapMs, withEvent } from "./goalForm";
import type { Goal } from "./types";

const filled = { ...emptyGoalForm(), time: "1:10.5", date: "2026-12-01" };

describe("goal form", () => {
  it("needs a readable time and a date", () => {
    expect(goalFormErrors(emptyGoalForm())).toEqual({ time: true, date: true });
    expect(goalFormErrors({ ...filled, time: "fast" })).toEqual({ time: true });
    expect(goalFormErrors(filled)).toEqual({});
  });

  it("builds the payload with the time in ms and blank track and notes as null", () => {
    expect(goalCreatePayload({ ...filled, notes: "  " })).toEqual({
      event_key: "1km",
      start_type: "standing",
      target_time_ms: 70_500,
      target_date: "2026-12-01",
      track_id: null,
      notes: null,
    });
    expect(goalCreatePayload({ ...filled, trackId: "t1", notes: " Worlds " })).toMatchObject({ track_id: "t1", notes: "Worlds" });
    expect(goalCreatePayload(emptyGoalForm())).toBeNull();
  });

  it("an update never carries the event or start", () => {
    expect(goalUpdatePayload(filled)).toEqual({ target_time_ms: 70_500, target_date: "2026-12-01", track_id: null, notes: null });
  });

  it("switching to an event without the current start falls back to its own", () => {
    expect(withEvent(filled, "f200").startType).toBe("flying");
    expect(withEvent(filled, "2km").startType).toBe("standing");
  });

  it("says where the date stands", () => {
    expect(dueState(12, false)).toBe("upcoming");
    expect(dueState(0, false)).toBe("today");
    expect(dueState(-3, false)).toBe("overdue");
    expect(dueState(-3, true)).toBe("reached");
  });

  it("compares the prediction with the target", () => {
    const goal = { target_time_ms: 70_000, prediction: { time_ms: 68_500 } } as Goal;
    expect(predictedGapMs(goal)).toBe(-1_500);
    expect(predictedGapMs({ ...goal, prediction: null })).toBeNull();
  });
});
