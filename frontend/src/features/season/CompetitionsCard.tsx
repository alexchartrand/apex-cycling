import { Flag, Pencil, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { errorMessage } from "../../api/errors";
import { Badge, Button, Card, ConfirmDialog, Dialog, IconButton, Input, Select, SkeletonGroup, Textarea, Tooltip, useToast } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { useGoals } from "../goals/useGoals";
import { formatRecordTime } from "../records/timeInput";
import type { StandardEventKey } from "../records/types";
import { competitionFormErrors, competitionFormFrom, competitionPayload, emptyCompetitionForm, type CompetitionForm } from "./season";
import type { Competition, Priority } from "./types";
import { useCountdownLabel } from "./useCountdownLabel";
import { useCompetitions, useDeleteCompetition, useSaveCompetition } from "./useSeason";
import "./Season.css";

const PRIORITIES: Priority[] = ["A", "B", "C"];

/** The race calendar: coming races with the days to go and the taper, then the past ones. */
export function CompetitionsCard({ athleteId }: { athleteId: string }) {
  const { t } = useTranslation("season");
  const { t: tc } = useTranslation("common");
  const { toast } = useToast();
  const competitions = useCompetitions(athleteId);
  const remove = useDeleteCompetition(athleteId);
  const [editing, setEditing] = useState<Competition | "new" | null>(null);
  const [deleting, setDeleting] = useState<Competition | null>(null);

  return (
    <Card
      title={t("races.title")}
      as="section"
      actions={
        <Button size="sm" variant="secondary" icon={<Plus aria-hidden />} onClick={() => setEditing("new")}>
          {t("races.add")}
        </Button>
      }
    >
      <p className="season__hint">{t("races.description")}</p>
      {competitions.isLoading && <SkeletonGroup lines={3} />}
      {competitions.isError && <p role="alert">{tc("loadError")}</p>}
      {competitions.data?.length === 0 && <p className="season__empty">{t("races.empty")}</p>}
      <ul className="season__list">
        {competitions.data?.map((competition) => (
          <RaceRow key={competition.id} race={competition} onEdit={() => setEditing(competition)} onDelete={() => setDeleting(competition)} />
        ))}
      </ul>

      {editing && (
        <CompetitionDialog
          key={editing === "new" ? "new" : editing.id}
          athleteId={athleteId}
          competition={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
        />
      )}
      <ConfirmDialog
        open={deleting != null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={t("races.delete.title")}
        description={t("races.delete.body", { name: deleting?.name ?? "" })}
        confirmLabel={tc("delete")}
        cancelLabel={tc("cancel")}
        tone="danger"
        onConfirm={async () => {
          try {
            await remove.mutateAsync(deleting!.id);
            toast({ title: t("races.delete.done"), tone: "success" });
          } catch (error) {
            toast({ title: errorMessage(error), tone: "error" });
            throw error;
          }
        }}
      />
    </Card>
  );
}

function RaceRow({ race, onEdit, onDelete }: { race: Competition; onEdit: () => void; onDelete: () => void }) {
  const { t } = useTranslation("season");
  const { t: tr } = useTranslation("records");
  const fmt = useFormat();
  const countdown = useCountdownLabel();
  const toTaper = race.days_to_taper;

  return (
    <li className={race.phase === "past" ? "season__item season__item--past" : "season__item"}>
      <div className="season__item-head">
        <div className="season__item-title">
          <strong>{race.name}</strong>
          <span className="season__sub">
            {fmt.date(race.competition_date, "weekday")}
            {race.location ? ` · ${race.location}` : ""}
          </span>
        </div>
        <span className="season__actions">
          <Tooltip content={t("races.edit")}>
            <IconButton size="sm" aria-label={`${t("races.edit")} — ${race.name}`} onClick={onEdit}>
              <Pencil aria-hidden />
            </IconButton>
          </Tooltip>
          <Tooltip content={t("races.remove")}>
            <IconButton size="sm" aria-label={`${t("races.remove")} — ${race.name}`} onClick={onDelete}>
              <Trash2 aria-hidden />
            </IconButton>
          </Tooltip>
        </span>
      </div>
      <p className="season__badges">
        <Badge tone={race.phase === "taper" || race.phase === "race_day" ? "highlight" : race.phase === "past" ? "neutral" : "accent"} icon={<Flag aria-hidden />}>
          {countdown(race)}
        </Badge>
        <Badge>{t("races.priorityBadge", { priority: race.priority })}</Badge>
        {race.phase === "taper" && <Badge tone="highlight">{t("races.inTaper")}</Badge>}
        {toTaper != null && <span className="season__sub">{t("races.taperIn", { count: toTaper })}</span>}
        {race.taper_starts_on && race.phase === "taper" && (
          <span className="season__sub">{t("races.taperSince", { date: fmt.date(race.taper_starts_on, "medium") })}</span>
        )}
      </p>
      {race.goal && (
        <p className="season__sub">
          {t("races.aiming", {
            event: tr(`events.${race.goal.event_key as StandardEventKey}`),
            time: formatRecordTime(race.goal.target_time_ms, fmt),
          })}
        </p>
      )}
      {race.race_session_id && (
        <p className="season__sub">
          <Link to={`/sessions/${race.race_session_id}`}>{t("races.openSession")}</Link>
        </p>
      )}
      {race.notes && <p className="season__notes">{race.notes}</p>}
    </li>
  );
}

function CompetitionDialog({ athleteId, competition, onClose }: { athleteId: string; competition: Competition | null; onClose: () => void }) {
  const { t } = useTranslation("season");
  const { t: tr } = useTranslation("records");
  const { t: tc } = useTranslation("common");
  const fmt = useFormat();
  const { toast } = useToast();
  const goals = useGoals(athleteId);
  const save = useSaveCompetition(athleteId);
  const [form, setForm] = useState<CompetitionForm>(() => (competition ? competitionFormFrom(competition) : emptyCompetitionForm()));
  const [showErrors, setShowErrors] = useState(false);
  const errors = competitionFormErrors(form);
  const set = <K extends keyof CompetitionForm>(key: K, value: CompetitionForm[K]) => setForm((current) => ({ ...current, [key]: value }));

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const payload = competitionPayload(form);
    if (!payload) {
      setShowErrors(true);
      return;
    }
    try {
      await save.mutateAsync({ id: competition?.id, payload });
      toast({ title: t("races.saved"), tone: "success" });
      onClose();
    } catch {
      // shown in the form
    }
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={competition ? t("races.dialog.editTitle") : t("races.dialog.addTitle")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {tc("cancel")}
          </Button>
          <Button type="submit" form="competition-form" loading={save.isPending}>
            {tc("save")}
          </Button>
        </>
      }
    >
      <form id="competition-form" className="season__form" onSubmit={handleSubmit} noValidate>
        <Input
          label={t("races.dialog.name")}
          value={form.name}
          maxLength={120}
          autoFocus={!competition}
          error={showErrors && errors.name ? t("races.dialog.nameInvalid") : undefined}
          onChange={(e) => set("name", e.target.value)}
        />
        <div className="season__form-row">
          <Input
            label={t("races.dialog.date")}
            type="date"
            value={form.date}
            error={showErrors && errors.date ? t("races.dialog.dateInvalid") : undefined}
            onChange={(e) => set("date", e.target.value)}
            required
          />
          <Select label={t("races.dialog.priority")} hint={t("races.dialog.priorityHint")} value={form.priority} onChange={(e) => set("priority", e.target.value as Priority)}>
            {PRIORITIES.map((priority) => (
              <option key={priority} value={priority}>
                {t(`races.priority.${priority}`)}
              </option>
            ))}
          </Select>
        </div>
        <Input label={t("races.dialog.location")} value={form.location} maxLength={120} onChange={(e) => set("location", e.target.value)} />
        <Select label={t("races.dialog.goal")} hint={t("races.dialog.goalHint")} value={form.goalId} onChange={(e) => set("goalId", e.target.value)}>
          <option value="">{t("races.dialog.noGoal")}</option>
          {goals.data?.map((goal) => (
            <option key={goal.id} value={goal.id}>
              {tr(`events.${goal.event_key as StandardEventKey}`)} · {tr(`startTypes.${goal.start_type}`)} · {formatRecordTime(goal.target_time_ms, fmt)}
            </option>
          ))}
        </Select>
        <Textarea label={t("races.dialog.notes")} rows={2} maxLength={2000} value={form.notes} onChange={(e) => set("notes", e.target.value)} />
        {save.isError && (
          <p className="season__error" role="alert">
            {errorMessage(save.error)}
          </p>
        )}
      </form>
    </Dialog>
  );
}
