import { Activity, CalendarPlus, MessageSquare, TriangleAlert, Trophy, UserPlus, type LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useFormat } from "../../i18n/useFormat";
import { formatRecordTime } from "../records/timeInput";
import type { AppNotification, NotificationKind } from "./types";

const ICONS: Record<NotificationKind, LucideIcon> = {
  new_pr: Trophy,
  sync_failed: TriangleAlert,
  comment: MessageSquare,
  coach_request: UserPlus,
  plan_added: CalendarPlus,
};

const text = (value: unknown): string => (typeof value === "string" ? value : "");

interface RecordItem {
  event_key?: string;
  time_ms?: number;
}

/** What a notification says, in the viewer's language, built from its payload. */
export function useNotificationText(notification: AppNotification): { title: string; body: string; Icon: LucideIcon } {
  const { t } = useTranslation(["notifications", "records"]);
  const fmt = useFormat();
  const { payload } = notification;
  const Icon = ICONS[notification.kind] ?? Activity;

  switch (notification.kind) {
    case "new_pr": {
      const items = (Array.isArray(payload.items) ? payload.items : []) as RecordItem[];
      const count = typeof payload.count === "number" ? payload.count : items.length;
      const first = items[0] ?? {};
      const event = first.event_key ? t(`records:events.${first.event_key as "lap"}`) : "";
      const session = text(payload.session_name);
      return count > 1
        ? { Icon, title: t("notifications:newPr.many", { count }), body: session }
        : {
            Icon,
            title: t("notifications:newPr.one", { event }),
            body: t("notifications:newPr.body", { session, time: first.time_ms ? formatRecordTime(first.time_ms, fmt) : "" }),
          };
    }
    case "sync_failed":
      return {
        Icon,
        title: t("notifications:syncFailed.title"),
        body: t("notifications:syncFailed.body", { code: text(payload.transponder_code), error: text(payload.error) }),
      };
    case "comment":
      return {
        Icon,
        title: t("notifications:comment.title", { author: text(payload.author_name) }),
        body: t("notifications:comment.body", { session: text(payload.session_name), excerpt: text(payload.excerpt) }),
      };
    case "coach_request": {
      const asked = payload.asked_role === "athlete" ? "fromAthlete" : "fromCoach";
      return {
        Icon,
        title: t("notifications:coachRequest.title"),
        body: t(`notifications:coachRequest.${asked}`, { name: text(payload.from_name) }),
      };
    }
    case "plan_added":
      return {
        Icon,
        title: t("notifications:planAdded.title"),
        body: t("notifications:planAdded.body", {
          author: text(payload.author_name),
          title: text(payload.title),
          date: payload.planned_date ? fmt.date(text(payload.planned_date), "dayMonth") : "",
        }),
      };
  }
}
