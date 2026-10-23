import { BellRing } from "lucide-react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Button, Card, Skeleton, useToast } from "../../components/ui";
import { NOTIFICATION_CHANNELS, NOTIFICATION_KINDS, type NotificationChannel, type NotificationKind } from "./types";
import { useNotificationPreferences, usePushConfig, useSaveNotificationPreferences } from "./useNotifications";
import { usePush } from "./usePush";
import "./Notifications.css";

/** Settings → Notifications: what to be told about, and where. */
export function NotificationSettings() {
  const { t } = useTranslation(["notifications", "common"]);
  const { toast } = useToast();
  const preferences = useNotificationPreferences();
  const save = useSaveNotificationPreferences();
  const pushConfig = usePushConfig();
  const push = usePush(pushConfig.data?.public_key ?? null);

  async function toggle(kind: NotificationKind, channel: NotificationChannel, enabled: boolean) {
    const current = preferences.data?.kinds[kind];
    if (!current) return;
    try {
      await save.mutateAsync({ [kind]: { ...current, [channel]: enabled } });
    } catch (err) {
      toast({ title: errorMessage(err), tone: "error" });
    }
  }

  async function handlePush(turnOn: boolean) {
    try {
      await (turnOn ? push.enable() : push.disable());
    } catch (err) {
      toast({ title: t("notifications:push.failed"), description: errorMessage(err), tone: "error" });
    }
  }

  const available: Record<NotificationChannel, boolean> = {
    in_app: true,
    push: preferences.data?.push_available ?? false,
    email: preferences.data?.email_available ?? false,
  };

  return (
    <div className="notif-settings">
      <Card title={t("notifications:settings.title")} as="section">
        <p className="notif-settings__description">{t("notifications:settings.description")}</p>
        {preferences.isLoading && <Skeleton height="12rem" />}
        {preferences.isError && <p role="alert">{t("common:loadError")}</p>}
        {preferences.data && (
          <table className="notif-settings__table" aria-label={t("notifications:settings.title")}>
            <thead>
              <tr>
                <th scope="col">{t("notifications:settings.event")}</th>
                {NOTIFICATION_CHANNELS.map((channel) => (
                  <th key={channel} scope="col">
                    {t(`notifications:channels.${channel}`)}
                    {!available[channel] && <span className="notif-settings__unavailable"> {t("notifications:settings.notSetUp")}</span>}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {NOTIFICATION_KINDS.map((kind) => (
                <tr key={kind}>
                  <th scope="row">
                    {t(`notifications:kinds.${kind}.label`)}
                    <span className="notif-settings__hint">{t(`notifications:kinds.${kind}.hint`)}</span>
                  </th>
                  {NOTIFICATION_CHANNELS.map((channel) => (
                    <td key={channel}>
                      <input
                        type="checkbox"
                        className="notif-settings__check"
                        aria-label={`${t(`notifications:kinds.${kind}.label`)} — ${t(`notifications:channels.${channel}`)}`}
                        checked={preferences.data.kinds[kind][channel]}
                        disabled={!available[channel] || save.isPending}
                        onChange={(event) => toggle(kind, channel, event.target.checked)}
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card title={t("notifications:push.title")} as="section">
        <p className="notif-settings__description">{t("notifications:push.description")}</p>
        {!pushConfig.data?.enabled && <p className="notif-settings__description">{t("notifications:push.serverOff")}</p>}
        {pushConfig.data?.enabled && push.state === "unsupported" && <p className="notif-settings__description">{t("notifications:push.unsupported")}</p>}
        {pushConfig.data?.enabled && push.state === "blocked" && <p className="notif-settings__description">{t("notifications:push.blocked")}</p>}
        {pushConfig.data?.enabled && (push.state === "off" || push.state === "on") && (
          <Button
            variant={push.state === "on" ? "secondary" : "primary"}
            icon={<BellRing aria-hidden />}
            disabled={push.busy}
            onClick={() => handlePush(push.state === "off")}
          >
            {push.state === "on" ? t("notifications:push.disable") : t("notifications:push.enable")}
          </Button>
        )}
        {pushConfig.data?.enabled && push.state === "on" && <p className="notif-settings__description">{t("notifications:push.on")}</p>}
      </Card>
    </div>
  );
}
