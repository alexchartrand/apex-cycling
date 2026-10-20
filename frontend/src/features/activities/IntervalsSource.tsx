import { useState, type FormEvent } from "react";
import { RefreshCw, Unplug, Waves } from "lucide-react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Badge, Button, Card, ConfirmDialog, Input, SkeletonGroup, useToast } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { SyncHistory } from "./SyncHistory";
import { useConnectIntervals, useDisconnectIntervals, useIntervalsStatus, useSyncIntervals } from "./useActivities";

export function IntervalsSource({ athleteId }: { athleteId: string }) {
  const { t } = useTranslation(["activities", "common"]);
  const fmt = useFormat();
  const { toast } = useToast();
  const status = useIntervalsStatus(athleteId);
  const connect = useConnectIntervals(athleteId);
  const sync = useSyncIntervals(athleteId);
  const disconnect = useDisconnectIntervals(athleteId);
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);

  const data = status.data;
  const active = data?.connected && data.active;

  async function handleConnect(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await connect.mutateAsync(apiKey.trim());
      setApiKey("");
      toast({ title: t("intervals.toasts.connected"), description: t("intervals.toasts.connectedDescription"), tone: "success" });
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function handleSync() {
    try {
      await sync.mutateAsync();
      toast({ title: t("intervals.toasts.syncing") });
    } catch (err) {
      toast({ title: errorMessage(err), tone: "error" });
    }
  }

  async function handleDisconnect() {
    try {
      await disconnect.mutateAsync();
      toast({ title: t("intervals.toasts.disconnected") });
    } catch (err) {
      toast({ title: errorMessage(err), tone: "error" });
      throw err;
    }
  }

  return (
    <Card eyebrow="intervals.icu" title={t("intervals.title")} actions={<Waves className="import-source__icon" aria-hidden />}>
      <p className="ui-card__hint">{t("intervals.description")}</p>
      {status.isLoading && <SkeletonGroup lines={2} />}
      {status.isError && <p role="alert">{t("common:loadError")}</p>}

      {data && active && (
        <>
          <div className="source-card__status">
            <Badge tone="positive">
              {data.intervals_athlete_name
                ? t("intervals.connectedAs", { name: data.intervals_athlete_name })
                : t("intervals.connectedGeneric")}
            </Badge>
            <span className="source-card__when">
              {data.last_synced_at ? t("intervals.lastSync", { when: fmt.relative(data.last_synced_at) }) : t("intervals.neverSynced")}
            </span>
          </div>
          <div className="source-card__actions">
            <Button size="sm" variant="secondary" icon={<RefreshCw aria-hidden />} loading={sync.isPending} onClick={handleSync}>
              {t("intervals.syncNow")}
            </Button>
            <Button size="sm" variant="ghost" icon={<Unplug aria-hidden />} onClick={() => setConfirming(true)}>
              {t("intervals.disconnect")}
            </Button>
          </div>
          <SyncHistory runs={data.runs} />
        </>
      )}

      {data && !active && (
        <>
          {data.connected && <p className="source-card__warning">{t("intervals.paused")}</p>}
          <form className="source-card__form" onSubmit={handleConnect}>
            <Input
              label={t("intervals.apiKey")}
              hint={t("intervals.apiKeyHint")}
              type="password"
              autoComplete="off"
              spellCheck={false}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              error={error ?? undefined}
              required
            />
            <Button type="submit" loading={connect.isPending} disabled={apiKey.trim().length < 8}>
              {t("intervals.connect")}
            </Button>
          </form>
          {data.connected && data.runs.length > 0 && <SyncHistory runs={data.runs} limit={2} />}
        </>
      )}

      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={t("intervals.disconnectTitle")}
        description={t("intervals.disconnectDescription")}
        confirmLabel={t("intervals.disconnect")}
        cancelLabel={t("common:cancel")}
        tone="danger"
        onConfirm={handleDisconnect}
      />
    </Card>
  );
}
