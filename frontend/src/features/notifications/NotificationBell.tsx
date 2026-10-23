import { Bell } from "lucide-react";
import { Popover } from "radix-ui";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { useMyAthlete } from "../athletes/useAthlete";
import { setViewingAthleteId } from "../athletes/viewing";
import { useFormat } from "../../i18n/useFormat";
import { Button, Skeleton } from "../../components/ui";
import { useNotificationText } from "./NotificationItem";
import { notificationTarget } from "./notificationTarget";
import type { AppNotification } from "./types";
import { useMarkRead, useNotificationList, useUnreadCount } from "./useNotifications";
import "./Notifications.css";

/**
 * The bell: unread count on it, the latest notifications in a panel. `row`
 * is the sidebar entry (label + count), `icon` the phone top bar's button.
 */
export function NotificationBell({ variant }: { variant: "row" | "compact" | "icon" }) {
  const { t } = useTranslation("notifications");
  const [open, setOpen] = useState(false);
  const unread = useUnreadCount();
  const list = useNotificationList(open);
  const markRead = useMarkRead();
  const label = unread > 0 ? t("bellUnread", { count: unread }) : t("bell");

  const trigger =
    variant === "row" ? (
      <button type="button" className="shell__link notif-trigger" aria-label={label}>
        <Bell aria-hidden />
        <span>{t("bell")}</span>
        {unread > 0 && <span className="shell__badge">{unread > 9 ? "9+" : unread}</span>}
      </button>
    ) : (
      <button type="button" className="notif-trigger notif-trigger--icon shell__link" aria-label={label}>
        <Bell aria-hidden />
        {unread > 0 && <span className={variant === "icon" ? "notif-trigger__count" : "shell__dot"}>{variant === "icon" ? (unread > 9 ? "9+" : unread) : null}</span>}
      </button>
    );

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>{trigger}</Popover.Trigger>
      <Popover.Portal>
        <Popover.Content className="notif-panel" align={variant === "icon" ? "end" : "start"} side={variant === "icon" ? "bottom" : "right"} sideOffset={8} collisionPadding={12}>
          <header className="notif-panel__header">
            <h2 className="notif-panel__title">{t("title")}</h2>
            <Button variant="ghost" size="sm" disabled={unread === 0 || markRead.isPending} onClick={() => markRead.mutate(undefined)}>
              {t("markAllRead")}
            </Button>
          </header>
          {list.isLoading && <Skeleton height="6rem" />}
          {list.isError && <p role="alert" className="notif-panel__note">{t("loadError")}</p>}
          {list.data?.length === 0 && <p className="notif-panel__note">{t("empty")}</p>}
          {list.data && list.data.length > 0 && (
            <ul className="notif-panel__list">
              {list.data.map((notification) => (
                <li key={notification.id}>
                  <NotificationRow notification={notification} onOpened={() => setOpen(false)} />
                </li>
              ))}
            </ul>
          )}
          <Link to="/settings/notifications" className="notif-panel__footer" onClick={() => setOpen(false)}>
            {t("settingsLink")}
          </Link>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

function NotificationRow({ notification, onOpened }: { notification: AppNotification; onOpened: () => void }) {
  const fmt = useFormat();
  const navigate = useNavigate();
  const me = useMyAthlete().data;
  const markRead = useMarkRead();
  const { title, body, Icon } = useNotificationText(notification);
  const unread = notification.read_at === null;

  function open() {
    const target = notificationTarget(notification);
    // A coach's athlete's thread is only reachable while viewing as them.
    if (target.athleteId && target.athleteId !== me?.id) setViewingAthleteId(target.athleteId);
    if (unread) markRead.mutate([notification.id]);
    onOpened();
    navigate(target.to);
  }

  return (
    <button type="button" className={unread ? "notif-row notif-row--unread" : "notif-row"} onClick={open}>
      <Icon className="notif-row__icon" aria-hidden />
      <span className="notif-row__text">
        <span className="notif-row__title">{title}</span>
        <span className="notif-row__body">{body}</span>
        <span className="notif-row__when">{fmt.relative(notification.created_at)}</span>
      </span>
      {unread && <span className="notif-row__dot" aria-hidden />}
    </button>
  );
}
