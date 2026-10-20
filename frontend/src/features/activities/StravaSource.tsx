import { useState } from "react";
import { Activity, RefreshCw, Unplug } from "lucide-react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Badge, Button, Card, ConfirmDialog, SkeletonGroup, useToast } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { SyncHistory } from "./SyncHistory";
import { useDisconnectStrava, useStartStravaAuthorization, useStravaStatus, useSyncStrava } from "./useActivities";

export type StravaReturn = "connected" | "denied" | "error";

export function StravaSource({ athleteId, returned }: { athleteId: string; returned?: StravaReturn | null }) {
  const { t } = useTranslation(["activities", "common"]);
  const fmt = useFormat();
  const { toast } = useToast();
  const status = useStravaStatus(athleteId);
  const authorize = useStartStravaAuthorization(athleteId);
  const sync = useSyncStrava(athleteId);
  const disconnect = useDisconnectStrava(athleteId);
  const [confirming, setConfirming] = useState(false);

  const data = status.data;
  const active = data?.connected && data.active;

  async function handleConnect() {
    try {
      const { url } = await authorize.mutateAsync();
      window.location.assign(url);
    } catch (err) {
      toast({ title: errorMessage(err), tone: "error" });
    }
  }

  async function handleSync() {
    try {
      await sync.mutateAsync();
      toast({ title: t("strava.toasts.syncing") });
    } catch (err) {
      toast({ title: errorMessage(err), tone: "error" });
    }
  }

  async function handleDisconnect() {
    try {
      await disconnect.mutateAsync();
      toast({ title: t("strava.toasts.disconnected") });
    } catch (err) {
      toast({ title: errorMessage(err), tone: "error" });
      throw err;
    }
  }

  return (
    <Card eyebrow="strava" title={t("strava.title")} actions={<Activity className="import-source__icon" aria-hidden />}>
      <p className="ui-card__hint">{t("strava.description")}</p>
      {returned && (
        <p className={`source-card__banner source-card__banner--${returned}`} role="status">
          {t(`strava.banner.${returned}`)}
        </p>
      )}
      {status.isLoading && <SkeletonGroup lines={2} />}
      {status.isError && <p role="alert">{t("common:loadError")}</p>}

      {data && !data.available && <p className="source-card__note">{t("strava.unavailable")}</p>}

      {data?.available && (
        <>
          <p className="source-card__note">{t("strava.ownerOnly")}</p>
          {active ? (
            <>
              <div className="source-card__status">
                <Badge tone="positive">
                  {data.strava_athlete_name ? t("strava.connectedAs", { name: data.strava_athlete_name }) : t("strava.connectedGeneric")}
                </Badge>
                <span className="source-card__when">
                  {data.last_synced_at ? t("strava.lastSync", { when: fmt.relative(data.last_synced_at) }) : t("strava.neverSynced")}
                </span>
              </div>
              <div className="source-card__actions">
                <Button size="sm" variant="secondary" icon={<RefreshCw aria-hidden />} loading={sync.isPending} onClick={handleSync}>
                  {t("strava.syncNow")}
                </Button>
                <Button size="sm" variant="ghost" icon={<Unplug aria-hidden />} onClick={() => setConfirming(true)}>
                  {t("strava.disconnect")}
                </Button>
              </div>
              <SyncHistory runs={data.runs} />
            </>
          ) : (
            <>
              {data.connected && <p className="source-card__warning">{t("strava.paused")}</p>}
              <div className="source-card__actions">
                <Button loading={authorize.isPending} onClick={handleConnect}>
                  {data.connected ? t("strava.reconnect") : t("strava.connect")}
                </Button>
              </div>
            </>
          )}
          <p className="source-card__note">{t("strava.poweredBy")}</p>
        </>
      )}

      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={t("strava.disconnectTitle")}
        description={t("strava.disconnectDescription")}
        confirmLabel={t("strava.disconnect")}
        cancelLabel={t("common:cancel")}
        tone="danger"
        onConfirm={handleDisconnect}
      />
    </Card>
  );
}
