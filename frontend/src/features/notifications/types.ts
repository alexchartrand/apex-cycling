export type NotificationKind = "new_pr" | "sync_failed" | "comment" | "coach_request" | "plan_added";

export const NOTIFICATION_KINDS: NotificationKind[] = ["new_pr", "comment", "coach_request", "plan_added", "sync_failed"];
export const NOTIFICATION_CHANNELS = ["in_app", "push", "email"] as const;
export type NotificationChannel = (typeof NOTIFICATION_CHANNELS)[number];

/** One entry of the bell. `payload` holds names, ids and times — the text is built here, in the viewer's language. */
export interface AppNotification {
  id: string;
  kind: NotificationKind;
  payload: Record<string, unknown>;
  created_at: string;
  read_at: string | null;
}

export type ChannelPreferences = Record<NotificationChannel, boolean>;

export interface NotificationPreferences {
  kinds: Record<NotificationKind, ChannelPreferences>;
  /** What the server can send: no SMTP / VAPID keys means that channel does nothing. */
  email_available: boolean;
  push_available: boolean;
}

export interface PushConfig {
  enabled: boolean;
  public_key: string | null;
}
