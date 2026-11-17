import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Button, Dialog, Input, Select, useToast } from "../../components/ui";
import { ACTIVITY_TYPES, AUTO_TYPE, identityChanges } from "./activityTypes";
import type { Activity } from "./types";
import { useUpdateActivity } from "./useActivities";

/** Rename an activity and say what kind of training it was (the data owner only). */
export function ActivityEditDialog({ athleteId, activity, onClose }: { athleteId: string; activity: Activity; onClose: () => void }) {
  const { t } = useTranslation(["activities", "common"]);
  const { toast } = useToast();
  const update = useUpdateActivity(athleteId, activity.id);
  const [name, setName] = useState(activity.name ?? "");
  const [type, setType] = useState<string>(activity.activity_type_manual ? activity.activity_type : AUTO_TYPE);
  const changes = identityChanges(activity, name, type);
  const dirty = Object.keys(changes).length > 0;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!dirty) return onClose();
    try {
      await update.mutateAsync(changes);
      toast({ title: t("activity.rename.saved"), tone: "success" });
      onClose();
    } catch {
      // shown inside the dialog
    }
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={t("activity.rename.title")}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t("common:cancel")}
          </Button>
          <Button type="submit" form="activity-identity-form" loading={update.isPending} disabled={!dirty}>
            {t("common:save")}
          </Button>
        </>
      }
    >
      <form id="activity-identity-form" className="activity-identity" onSubmit={handleSubmit}>
        <Input
          label={t("activity.edit.name")}
          value={name}
          maxLength={255}
          placeholder={t(`types.${activity.activity_type}.untitled`, { date: "…" })}
          onChange={(e) => setName(e.target.value)}
          autoFocus
        />
        <Select label={t("types.label")} hint={t("types.autoHint")} value={type} onChange={(e) => setType(e.target.value)}>
          <option value={AUTO_TYPE}>
            {activity.activity_type_manual ? t("types.detected") : t("types.auto", { type: t(`types.${activity.activity_type}.name`) })}
          </option>
          {ACTIVITY_TYPES.map((option) => (
            <option key={option} value={option}>
              {t(`types.${option}.name`)}
            </option>
          ))}
        </Select>
        {update.isError && <p role="alert">{errorMessage(update.error)}</p>}
      </form>
    </Dialog>
  );
}
