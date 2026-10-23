import { useState } from "react";
import { ExternalLink, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Button, ConfirmDialog, useToast } from "../../components/ui";
import type { Activity } from "./types";
import { useDeleteActivity } from "./useActivities";

/** Header actions for a recording: back to where it came from, and delete (the data owner only). */
export function RecordingActions({
  athleteId,
  activity,
  canEdit,
  onDeleted,
}: {
  athleteId: string;
  activity: Activity;
  canEdit: boolean;
  onDeleted: () => void;
}) {
  const { t } = useTranslation(["activities", "common"]);
  const { toast } = useToast();
  const remove = useDeleteActivity(athleteId);
  const [confirming, setConfirming] = useState(false);

  async function handleDelete() {
    try {
      await remove.mutateAsync(activity.id);
      toast({ title: t("activity.delete.deleted") });
      onDeleted();
    } catch (err) {
      toast({ title: errorMessage(err), tone: "error" });
      throw err;
    }
  }

  return (
    <>
      {activity.external_url && (
        <a className="btn btn--secondary btn--md" href={activity.external_url} target="_blank" rel="noreferrer">
          <ExternalLink aria-hidden />
          <span className="btn__label">{activity.source === "strava" ? t("activity.viewOnStrava") : t("activity.viewOnIntervals")}</span>
        </a>
      )}
      {canEdit && (
        <Button variant="ghost" icon={<Trash2 aria-hidden />} onClick={() => setConfirming(true)}>
          {t("activity.delete.action")}
        </Button>
      )}
      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={t("activity.delete.title")}
        description={t("activity.delete.description")}
        confirmLabel={t("activity.delete.action")}
        cancelLabel={t("common:cancel")}
        tone="danger"
        onConfirm={handleDelete}
      />
    </>
  );
}
