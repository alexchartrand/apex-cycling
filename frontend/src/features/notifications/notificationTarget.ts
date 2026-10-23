import type { AppNotification } from "./types";

export interface NotificationTarget {
  /** Where the notification leads. */
  to: string;
  /** The athlete whose data that page shows, when it isn't the viewer's own (a coach's athlete). */
  athleteId: string | null;
}

const text = (value: unknown): string => (typeof value === "string" ? value : "");

export function notificationTarget(notification: AppNotification): NotificationTarget {
  const { payload } = notification;
  const session = encodeURIComponent(text(payload.external_event_id));
  switch (notification.kind) {
    case "new_pr":
      return { to: `/sessions/${session}`, athleteId: null };
    case "comment":
      return { to: `/sessions/${session}?tab=comments`, athleteId: text(payload.athlete_id) || null };
    case "sync_failed":
      return { to: "/import", athleteId: null };
    case "coach_request":
      return { to: "/coach", athleteId: null };
    case "plan_added":
      return { to: "/", athleteId: null };
  }
}
