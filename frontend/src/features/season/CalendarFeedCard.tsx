import { CalendarSync, Copy } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Button, Card, ConfirmDialog, Input, useToast } from "../../components/ui";
import { useCalendarFeed, useCloseCalendarFeed, useMakeCalendarFeed } from "./useSeason";
import "./Season.css";

/** The secret link a phone calendar subscribes to. Only the athlete's side sees it; the link is shown once. */
export function CalendarFeedCard({ athleteId }: { athleteId: string }) {
  const { t } = useTranslation("season");
  const { t: tc } = useTranslation("common");
  const { toast } = useToast();
  const feed = useCalendarFeed(athleteId);
  const make = useMakeCalendarFeed(athleteId);
  const close = useCloseCalendarFeed(athleteId);
  const [url, setUrl] = useState<string | null>(null);
  const [replacing, setReplacing] = useState(false);
  const [closing, setClosing] = useState(false);

  // A coach looking at the athlete's page gets a 403: it isn't theirs to manage.
  if (!feed.data) return null;

  async function create() {
    try {
      const made = await make.mutateAsync();
      setUrl(made.url);
    } catch (error) {
      toast({ title: errorMessage(error), tone: "error" });
    }
  }

  async function copy() {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      toast({ title: t("calendar.copied"), tone: "success" });
    } catch {
      toast({ title: t("calendar.copyFailed"), tone: "error" });
    }
  }

  return (
    <Card title={t("calendar.title")} as="section">
      <div className="season__body">
        <p className="season__hint">{t("calendar.description")}</p>
        {url && (
          <div className="season__link">
            <Input label={t("calendar.link")} value={url} readOnly onFocus={(e) => e.currentTarget.select()} hint={t("calendar.onceOnly")} />
            <Button variant="secondary" icon={<Copy aria-hidden />} onClick={copy}>
              {t("calendar.copy")}
            </Button>
          </div>
        )}
        {feed.data.enabled ? (
          <div className="season__actions-row">
            <p className="season__sub">{url ? t("calendar.subscribeHint") : t("calendar.active")}</p>
            <Button variant="secondary" icon={<CalendarSync aria-hidden />} onClick={() => setReplacing(true)}>
              {t("calendar.replace")}
            </Button>
            <Button variant="ghost" onClick={() => setClosing(true)}>
              {t("calendar.turnOff")}
            </Button>
          </div>
        ) : (
          <div className="season__actions-row">
            <Button icon={<CalendarSync aria-hidden />} onClick={create} loading={make.isPending}>
              {t("calendar.create")}
            </Button>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={replacing}
        onOpenChange={setReplacing}
        title={t("calendar.replaceTitle")}
        description={t("calendar.replaceBody")}
        confirmLabel={t("calendar.replace")}
        cancelLabel={tc("cancel")}
        onConfirm={create}
      />
      <ConfirmDialog
        open={closing}
        onOpenChange={setClosing}
        title={t("calendar.turnOffTitle")}
        description={t("calendar.turnOffBody")}
        confirmLabel={t("calendar.turnOff")}
        cancelLabel={tc("cancel")}
        tone="danger"
        onConfirm={async () => {
          try {
            await close.mutateAsync();
            setUrl(null);
            toast({ title: t("calendar.turnedOff"), tone: "success" });
          } catch (error) {
            toast({ title: errorMessage(error), tone: "error" });
            throw error;
          }
        }}
      />
    </Card>
  );
}
