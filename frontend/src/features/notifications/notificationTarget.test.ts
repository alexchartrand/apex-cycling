import { describe, expect, it } from "vitest";
import { notificationTarget } from "./notificationTarget";
import type { AppNotification, NotificationKind } from "./types";

function note(kind: NotificationKind, payload: Record<string, unknown> = {}): AppNotification {
  return { id: "n1", kind, payload, created_at: "2026-10-23T10:00:00Z", read_at: null };
}

describe("notificationTarget", () => {
  it("opens the session of a record", () => {
    expect(notificationTarget(note("new_pr", { external_event_id: "evt 1" }))).toEqual({ to: "/sessions/evt%201", athleteId: null });
  });

  it("opens a comment thread as the athlete it is about", () => {
    expect(notificationTarget(note("comment", { external_event_id: "e1", athlete_id: "a9" }))).toEqual({
      to: "/sessions/e1?tab=comments",
      athleteId: "a9",
    });
    expect(notificationTarget(note("comment", { external_event_id: "e1" })).athleteId).toBeNull();
  });

  it("sends the rest to the page that handles them", () => {
    expect(notificationTarget(note("sync_failed")).to).toBe("/import");
    expect(notificationTarget(note("coach_request")).to).toBe("/coach");
    expect(notificationTarget(note("plan_added")).to).toBe("/");
  });
});
