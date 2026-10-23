import { apiFetch } from "../../api/client";
import type { AppNotification, ChannelPreferences, NotificationKind, NotificationPreferences, PushConfig } from "./types";

export function listNotifications(): Promise<AppNotification[]> {
  return apiFetch<AppNotification[]>("/notifications");
}

export async function getUnreadCount(): Promise<number> {
  return (await apiFetch<{ count: number }>("/notifications/unread-count")).count;
}

/** Marks the given notifications read, or every one without ids. */
export function markRead(ids?: string[]): Promise<void> {
  return apiFetch<void>("/notifications/read", { method: "POST", body: JSON.stringify(ids ? { ids } : {}) });
}

export function getPreferences(): Promise<NotificationPreferences> {
  return apiFetch<NotificationPreferences>("/notifications/preferences");
}

export function savePreferences(kinds: Partial<Record<NotificationKind, ChannelPreferences>>): Promise<NotificationPreferences> {
  return apiFetch<NotificationPreferences>("/notifications/preferences", { method: "PUT", body: JSON.stringify({ kinds }) });
}

export function getPushConfig(): Promise<PushConfig> {
  return apiFetch<PushConfig>("/notifications/push");
}

export function sendPushSubscription(subscription: PushSubscriptionJSON): Promise<void> {
  return apiFetch<void>("/notifications/push/subscriptions", { method: "POST", body: JSON.stringify(subscription) });
}

export function removePushSubscription(endpoint: string): Promise<void> {
  return apiFetch<void>("/notifications/push/unsubscribe", { method: "POST", body: JSON.stringify({ endpoint }) });
}
