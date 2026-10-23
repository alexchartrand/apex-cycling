import { useState } from "react";
import { Link2, Link2Off } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { errorMessage } from "../../api/errors";
import { Badge, Button, Card, Input, useToast } from "../../components/ui";
import { useSessions } from "../training/useTraining";
import type { Activity } from "./types";
import { useLinkActivitySession, useSessionSuggestion, useUnlinkActivitySession } from "./useActivities";

/**
 * Which sqorz session this ride contains, and how far the device clock is
 * from sqorz's. Linking puts the ride's power, heart rate and cadence on the
 * session's lap table, and the ride itself on the session's Ride tab (where
 * this panel then sits): unlinking sends it back to its own page.
 */
export function SessionLinkPanel({ athleteId, activity, canEdit }: { athleteId: string; activity: Activity; canEdit: boolean }) {
  const { t } = useTranslation(["activities", "common"]);
  const { toast } = useToast();
  const navigate = useNavigate();
  const sessions = useSessions(athleteId);
  const suggestion = useSessionSuggestion(athleteId, activity.id, canEdit && activity.external_event_id === null);
  const link = useLinkActivitySession(athleteId, activity.id);
  const unlink = useUnlinkActivitySession(athleteId, activity.id);
  const [offset, setOffset] = useState(String(activity.clock_offset_s));

  const linked = activity.external_event_id
    ? sessions.data?.find((s) => s.external_event_id === activity.external_event_id)
    : undefined;
  const offsetValue = Number(offset);
  const offsetValid = offset.trim() !== "" && Number.isFinite(offsetValue) && Math.abs(offsetValue) <= 3600;

  async function run(action: () => Promise<unknown>, message: string) {
    try {
      await action();
      toast({ title: message, tone: "success" });
    } catch (err) {
      toast({ title: errorMessage(err), tone: "error" });
    }
  }

  const proposed = suggestion.data;
  return (
    <Card as="section" title={t("activity.session.title")} actions={<Link2 className="import-source__icon" aria-hidden />}>
      {activity.external_event_id ? (
        <div className="session-link">
          <div className="source-card__status">
            <Badge tone="positive">{t("activity.session.linked", { name: linked?.event_name ?? "…" })}</Badge>
          </div>
          <p className="source-card__note">{t("activity.session.linkedDescription")}</p>
          {canEdit && (
            <>
              <form
                className="session-link__offset"
                onSubmit={(event) => {
                  event.preventDefault();
                  if (!offsetValid) return;
                  void run(
                    () => link.mutateAsync({ external_event_id: activity.external_event_id!, clock_offset_s: offsetValue }),
                    t("activity.session.toasts.offset"),
                  );
                }}
              >
                <Input
                  label={t("activity.session.offset")}
                  hint={`${t("activity.session.offsetHint")} ${activity.session_link_manual ? t("activity.session.offsetManual") : t("activity.session.offsetAuto")}.`}
                  type="number"
                  step="0.25"
                  value={offset}
                  onChange={(e) => setOffset(e.target.value)}
                />
                <Button type="submit" size="sm" variant="secondary" loading={link.isPending} disabled={!offsetValid || offsetValue === activity.clock_offset_s}>
                  {t("activity.session.saveOffset")}
                </Button>
              </form>
              <Button
                size="sm"
                variant="ghost"
                icon={<Link2Off aria-hidden />}
                loading={unlink.isPending}
                onClick={() =>
                  run(async () => {
                    await unlink.mutateAsync();
                    navigate(`/activities/${activity.id}`);
                  }, t("activity.session.toasts.unlinked"))
                }
              >
                {t("activity.session.unlink")}
              </Button>
            </>
          )}
        </div>
      ) : (
        <div className="session-link">
          <p className="source-card__note">{t("activity.session.unlinked")}</p>
          {canEdit && proposed?.external_event_id && (
            <div className="source-card__status">
              <span>{t("activity.session.suggestion", { name: proposed.event_name })}</span>
              <Button
                size="sm"
                loading={link.isPending}
                onClick={() => run(() => link.mutateAsync({ external_event_id: proposed.external_event_id! }), t("activity.session.toasts.linked"))}
              >
                {t("activity.session.linkIt")}
              </Button>
            </div>
          )}
          {canEdit && suggestion.data && !proposed?.external_event_id && <p className="source-card__note">{t("activity.session.noSuggestion")}</p>}
        </div>
      )}
    </Card>
  );
}
