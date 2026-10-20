import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Button, Card, Input, Select, Textarea, useToast } from "../../components/ui";
import type { Activity } from "./types";
import { useUpdateActivity } from "./useActivities";

const RPE_LEVELS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] as const;

/** The athlete's own name, effort rating and notes for a ride. */
export function ActivityNotes({ athleteId, activity }: { athleteId: string; activity: Activity }) {
  const { t } = useTranslation(["activities", "training"]);
  const { toast } = useToast();
  const update = useUpdateActivity(athleteId, activity.id);
  const [name, setName] = useState(activity.name ?? "");
  const [rpe, setRpe] = useState(activity.rpe == null ? "" : String(activity.rpe));
  const [notes, setNotes] = useState(activity.notes ?? "");
  const [error, setError] = useState<string | null>(null);

  const changes = {
    ...(name.trim() !== (activity.name ?? "") && { name: name.trim() || null }),
    ...(rpe !== (activity.rpe == null ? "" : String(activity.rpe)) && { rpe: rpe === "" ? null : Number(rpe) }),
    ...(notes !== (activity.notes ?? "") && { notes: notes.trim() === "" ? null : notes }),
  };
  const dirty = Object.keys(changes).length > 0;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!dirty) return;
    setError(null);
    try {
      await update.mutateAsync(changes);
      toast({ title: t("activity.edit.saved"), tone: "success" });
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <Card as="section" title={t("activity.edit.title")}>
      <form className="activity-notes" onSubmit={handleSubmit}>
        <Input label={t("activity.edit.name")} value={name} maxLength={255} onChange={(e) => setName(e.target.value)} />
        <Select label={t("activity.edit.rpe")} hint={t("activity.edit.rpeHint")} value={rpe} onChange={(e) => setRpe(e.target.value)}>
          <option value="">{t("activity.edit.rpeNone")}</option>
          {RPE_LEVELS.map((level) => (
            <option key={level} value={level}>
              {t(`training:notes.rpeLevels.l${level}`)}
            </option>
          ))}
        </Select>
        <Textarea label={t("activity.edit.notes")} rows={4} maxLength={5000} value={notes} onChange={(e) => setNotes(e.target.value)} />
        {error && <p role="alert">{error}</p>}
        <Button type="submit" loading={update.isPending} disabled={!dirty}>
          {t("activity.edit.save")}
        </Button>
      </form>
    </Card>
  );
}
