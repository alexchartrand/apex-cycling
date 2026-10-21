import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Badge, Button, Card, ConfirmDialog, Dialog, IconButton, Input, ProgressBar, Select, SkeletonGroup, Textarea, Tooltip, useToast } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { formatRecordTime } from "../records/timeInput";
import { EVENT_START_TYPES, STANDARD_EVENT_KEYS, type StandardEventKey } from "../records/types";
import { useTracks } from "../training/useTraining";
import type { TrackSummary } from "../training/types";
import { dueState, emptyGoalForm, goalCreatePayload, goalFormErrors, goalFormFrom, goalUpdatePayload, predictedGapMs, withEvent, type GoalForm } from "./goalForm";
import type { Goal } from "./types";
import { useDeleteGoal, useGoals, useSaveGoal } from "./useGoals";
import "./Goals.css";

/** The athlete's goals: the best so far against each target, and the time the latest power and CdA predict. */
export function GoalsCard({ athleteId }: { athleteId: string }) {
  const { t } = useTranslation("goals");
  const { t: tc } = useTranslation("common");
  const { toast } = useToast();
  const goals = useGoals(athleteId);
  const tracks = useTracks(athleteId);
  const remove = useDeleteGoal(athleteId);
  const [editing, setEditing] = useState<Goal | "new" | null>(null);
  const [deleting, setDeleting] = useState<Goal | null>(null);

  return (
    <Card
      title={t("title")}
      actions={
        <Button size="sm" variant="secondary" icon={<Plus aria-hidden />} onClick={() => setEditing("new")}>
          {t("add")}
        </Button>
      }
    >
      {goals.isLoading && <SkeletonGroup lines={3} />}
      {goals.isError && <p role="alert">{tc("loadError")}</p>}
      {goals.data?.length === 0 && <p className="goals__empty">{t("empty")}</p>}
      <ul className="goals">
        {goals.data?.map((goal) => (
          <GoalRow key={goal.id} goal={goal} onEdit={() => setEditing(goal)} onDelete={() => setDeleting(goal)} />
        ))}
      </ul>

      {editing && (
        <GoalDialog
          key={editing === "new" ? "new" : editing.id}
          athleteId={athleteId}
          tracks={tracks.data ?? []}
          goal={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
        />
      )}
      <ConfirmDialog
        open={deleting != null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={t("delete.title")}
        description={t("delete.body")}
        confirmLabel={tc("delete")}
        cancelLabel={tc("cancel")}
        tone="danger"
        onConfirm={async () => {
          try {
            await remove.mutateAsync(deleting!.id);
            toast({ title: t("delete.done"), tone: "success" });
          } catch (error) {
            toast({ title: errorMessage(error), tone: "error" });
            throw error;
          }
        }}
      />
    </Card>
  );
}

function GoalRow({ goal, onEdit, onDelete }: { goal: Goal; onEdit: () => void; onDelete: () => void }) {
  const { t } = useTranslation("goals");
  const { t: tr } = useTranslation("records");
  const fmt = useFormat();
  const time = (ms: number) => formatRecordTime(ms, fmt);
  const due = dueState(goal.days_left, goal.achieved);
  const title = `${tr(`events.${goal.event_key as StandardEventKey}`)} · ${tr(`startTypes.${goal.start_type}`)}`;
  const predictedGap = predictedGapMs(goal);

  return (
    <li className="goals__item">
      <div className="goals__head">
        <div className="goals__title">
          <strong>{title}</strong>
          <span className="goals__place">{goal.track_name ?? t("anyTrack")}</span>
        </div>
        <span className="goals__actions">
          <Tooltip content={t("edit")}>
            <IconButton size="sm" aria-label={`${t("edit")} — ${title}`} onClick={onEdit}>
              <Pencil aria-hidden />
            </IconButton>
          </Tooltip>
          <Tooltip content={t("remove")}>
            <IconButton size="sm" aria-label={`${t("remove")} — ${title}`} onClick={onDelete}>
              <Trash2 aria-hidden />
            </IconButton>
          </Tooltip>
        </span>
      </div>

      <div className="goals__numbers">
        <div>
          <span className="goals__label">{t("target")}</span>
          <span className="goals__value">{time(goal.target_time_ms)}</span>
        </div>
        <div>
          <span className="goals__label">{t("best")}</span>
          <span className="goals__value">{goal.best ? time(goal.best.time_ms) : "—"}</span>
        </div>
        <div>
          <span className="goals__label">{t("gap")}</span>
          <span className="goals__value">
            {goal.gap_ms == null ? "—" : goal.gap_ms <= 0 ? t("reached") : `+${fmt.seconds(goal.gap_ms)} s`}
          </span>
        </div>
      </div>

      {goal.progress != null && <ProgressBar value={goal.progress} label={t("progress", { event: title })} tone={goal.achieved ? "positive" : "goal"} />}

      <p className="goals__due">
        <Badge tone={due === "reached" ? "positive" : due === "overdue" ? "negative" : "neutral"}>
          {due === "upcoming" ? t("daysLeft", { count: goal.days_left }) : t(`due.${due}`)}
        </Badge>
        <span>{t("by", { date: fmt.date(goal.target_date, "medium") })}</span>
      </p>

      {goal.prediction ? (
        <p className="goals__prediction">
          {t("predicted", { time: time(goal.prediction.time_ms) })}
          {predictedGap != null && (
            <span className={predictedGap <= 0 ? "goals__beats" : undefined}>
              {" "}
              {predictedGap <= 0
                ? t("predictedBeats", { gap: fmt.seconds(-predictedGap) })
                : t("predictedShort", { gap: fmt.seconds(predictedGap) })}
            </span>
          )}
          <span className="goals__basis">
            {t("basis", {
              power: fmt.number(goal.prediction.power_w, 0),
              duration: fmt.duration(goal.prediction.power_duration_s),
              date: fmt.date(goal.prediction.power_on, "medium"),
              cda: fmt.number(goal.prediction.cda_m2, 3, 3),
              label: goal.prediction.cda_label,
            })}
          </span>
        </p>
      ) : (
        goal.prediction_problem && <p className="goals__basis">{t(`problems.${goal.prediction_problem}`)}</p>
      )}
      {goal.notes && <p className="goals__notes">{goal.notes}</p>}
    </li>
  );
}

function GoalDialog({ athleteId, tracks, goal, onClose }: { athleteId: string; tracks: TrackSummary[]; goal: Goal | null; onClose: () => void }) {
  const { t } = useTranslation("goals");
  const { t: tr } = useTranslation("records");
  const { t: tc } = useTranslation("common");
  const fmt = useFormat();
  const { toast } = useToast();
  const save = useSaveGoal(athleteId);
  const [form, setForm] = useState<GoalForm>(() => (goal ? goalFormFrom(goal, fmt) : emptyGoalForm()));
  const [showErrors, setShowErrors] = useState(false);
  const errors = goalFormErrors(form);
  const set = <K extends keyof GoalForm>(key: K, value: GoalForm[K]) => setForm((current) => ({ ...current, [key]: value }));

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const payload = goal ? goalUpdatePayload(form) : goalCreatePayload(form);
    if (!payload) {
      setShowErrors(true);
      return;
    }
    try {
      await save.mutateAsync({ goalId: goal?.id, payload });
      toast({ title: t("saved"), tone: "success" });
      onClose();
    } catch {
      // shown in the form
    }
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={goal ? t("dialog.editTitle") : t("dialog.addTitle")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {tc("cancel")}
          </Button>
          <Button type="submit" form="goal-form" loading={save.isPending}>
            {tc("save")}
          </Button>
        </>
      }
    >
      <form id="goal-form" className="goals__form" onSubmit={handleSubmit} noValidate>
        <div className="goals__form-row">
          <Select label={t("dialog.event")} value={form.eventKey} disabled={goal != null} onChange={(e) => setForm(withEvent(form, e.target.value as StandardEventKey))}>
            {STANDARD_EVENT_KEYS.map((key) => (
              <option key={key} value={key}>
                {tr(`events.${key}`)}
              </option>
            ))}
          </Select>
          <Select
            label={t("dialog.start")}
            value={form.startType}
            disabled={goal != null || EVENT_START_TYPES[form.eventKey].length === 1}
            onChange={(e) => set("startType", e.target.value as GoalForm["startType"])}
          >
            {EVENT_START_TYPES[form.eventKey].map((start) => (
              <option key={start} value={start}>
                {tr(`startTypes.${start}`)}
              </option>
            ))}
          </Select>
        </div>
        <div className="goals__form-row">
          <Input
            label={t("dialog.time")}
            value={form.time}
            inputMode="decimal"
            autoComplete="off"
            hint={t("dialog.timeHint")}
            error={showErrors && errors.time ? t("dialog.timeInvalid") : undefined}
            onChange={(e) => set("time", e.target.value)}
            autoFocus={!goal}
          />
          <Input
            label={t("dialog.date")}
            type="date"
            value={form.date}
            error={showErrors && errors.date ? t("dialog.dateInvalid") : undefined}
            onChange={(e) => set("date", e.target.value)}
            required
          />
        </div>
        <Select label={t("dialog.track")} hint={t("dialog.trackHint")} value={form.trackId} onChange={(e) => set("trackId", e.target.value)}>
          <option value="">{t("anyTrack")}</option>
          {tracks.map((track) => (
            <option key={track.id} value={track.id}>
              {track.name}
            </option>
          ))}
        </Select>
        <Textarea label={t("dialog.notes")} rows={2} maxLength={1000} value={form.notes} onChange={(e) => set("notes", e.target.value)} />
        {save.isError && (
          <p className="goals__error" role="alert">
            {errorMessage(save.error)}
          </p>
        )}
      </form>
    </Dialog>
  );
}
