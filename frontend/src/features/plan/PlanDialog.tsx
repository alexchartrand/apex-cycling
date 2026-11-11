import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { errorMessage } from "../../api/errors";
import { Button, Dialog, Input, Select, Textarea, useToast } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { formatRecordTime } from "../records/timeInput";
import { getWorkout } from "../workouts/api";
import { IntensityChart } from "../workouts/IntensityChart";
import { hasWattTargets, type Workout, type WorkoutSource } from "../workouts/types";
import { useEstimateFtp, useWorkoutEstimate, useWorkouts } from "../workouts/useWorkouts";
import { WorkoutSteps } from "../workouts/WorkoutSteps";
import { WorkoutTotals } from "../workouts/WorkoutTotals";
import { effortText, emptyPlanForm, planFormErrors, planFormFrom, planPayload, withLibraryWorkout, workoutGearLabels, type PlanForm } from "./planForm";
import type { PlannedSession } from "./types";
import { useSavePlan } from "./usePlan";
import "../workouts/Workouts.css";
import "./Plan.css";

const SOURCES: WorkoutSource[] = ["mine", "coach", "preset"];
/** The select's value while the plan keeps what it already has (its copy of a workout, or older efforts). */
const KEEP = "__keep";

/**
 * Plan a session on `date`, or edit `plan`; `workout` starts a new plan from
 * that library workout. A plan is always a library workout: it is chosen
 * first and shown read-only, since workouts are built and edited in the
 * library. The plan keeps its own copy of the steps, so later library edits
 * don't rewrite it. Remount it (key) per plan so its fields start fresh.
 */
export function PlanDialog({
  athleteId,
  date,
  plan,
  workout,
  onClose,
}: {
  athleteId: string;
  date: string;
  plan: PlannedSession | null;
  workout?: Workout;
  onClose: () => void;
}) {
  const { t } = useTranslation("plan");
  const { t: tw } = useTranslation("workouts");
  const { t: tr } = useTranslation("records");
  const { t: tc } = useTranslation("common");
  const fmt = useFormat();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const save = useSavePlan(athleteId);
  const library = useWorkouts({});
  const ftp = useEstimateFtp();
  const [form, setForm] = useState<PlanForm>(() => {
    if (plan) return planFormFrom(plan);
    const empty = emptyPlanForm(date);
    return workout ? withLibraryWorkout(empty, workout) : empty;
  });
  // What the plan had when the dialog opened stays a choice until another workout replaces it.
  const [kept, setKept] = useState(plan != null && (plan.workout != null || plan.targets.length > 0));
  const [picking, setPicking] = useState(false);
  const [showErrors, setShowErrors] = useState(false);
  const errors = planFormErrors(form);
  const set = <K extends keyof PlanForm>(key: K, value: PlanForm[K]) => setForm((current) => ({ ...current, [key]: value }));

  const estimate = useWorkoutEstimate(form.workout, ftp);

  async function pickWorkout(workoutId: string) {
    if (!workoutId || workoutId === KEEP) return;
    setPicking(true);
    try {
      const picked = await queryClient.fetchQuery({ queryKey: ["workout", workoutId], queryFn: () => getWorkout(workoutId) });
      setForm((current) => withLibraryWorkout(current, picked));
      setKept(false);
    } catch (error) {
      toast({ title: errorMessage(error), tone: "error" });
    } finally {
      setPicking(false);
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const payload = planPayload(form);
    if (!payload) {
      setShowErrors(true);
      return;
    }
    try {
      await save.mutateAsync({ planId: plan?.id, payload });
      toast({ title: t("saved"), tone: "success" });
      onClose();
    } catch {
      // shown in the form
    }
  }

  const workouts = library.data ?? [];
  const selected = kept ? KEEP : (form.sourceWorkoutId ?? "");
  const keptLabel = plan?.workout ? t("dialog.keepWorkout") : t("dialog.keepEfforts");
  const emptyLibrary = !library.isLoading && workouts.length === 0 && !kept && form.workout == null;

  return (
    <Dialog
      open
      size="lg"
      onOpenChange={(open) => !open && onClose()}
      title={plan ? t("dialog.editTitle") : t("dialog.addTitle")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {tc("cancel")}
          </Button>
          <Button type="submit" form="plan-form" loading={save.isPending}>
            {tc("save")}
          </Button>
        </>
      }
    >
      <form id="plan-form" className="plan-form" onSubmit={handleSubmit} noValidate>
        <Select
          label={t("dialog.workout")}
          value={selected}
          disabled={picking || library.isLoading}
          error={showErrors && errors.workout ? t("dialog.workoutRequired") : undefined}
          onChange={(e) => void pickWorkout(e.target.value)}
          autoFocus={!plan && !workout}
          required
        >
          {selected === "" && (
            <option value="" disabled>
              {t("dialog.pickWorkout")}
            </option>
          )}
          {kept && <option value={KEEP}>{keptLabel}</option>}
          {SOURCES.map((source) => {
            const ofSource = workouts.filter((w) => w.source === source);
            return ofSource.length === 0 ? null : (
              <optgroup key={source} label={tw(`sources.${source}`)}>
                {ofSource.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.source === "coach" && w.owner_name ? `${w.name} (${w.owner_name})` : w.name}
                  </option>
                ))}
              </optgroup>
            );
          })}
          {/* A workout opened from its own page that the list doesn't (yet) hold. */}
          {!kept && form.sourceWorkoutId && !workouts.some((w) => w.id === form.sourceWorkoutId) && workout && <option value={workout.id}>{workout.name}</option>}
        </Select>
        {emptyLibrary ? (
          <p className="plan-form__hint">
            {t("dialog.emptyLibrary")} <Link to="/workouts/new">{t("dialog.createWorkout")}</Link>
          </p>
        ) : (
          <p className="plan-form__hint">{t("dialog.workoutHint")}</p>
        )}

        <div className="plan-form__row plan-form__row--title">
          <Input
            label={t("dialog.title")}
            value={form.title}
            maxLength={120}
            placeholder={t("dialog.titlePlaceholder")}
            error={showErrors && errors.title ? t("dialog.titleRequired") : undefined}
            onChange={(e) => set("title", e.target.value)}
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
        <Textarea label={t("dialog.description")} rows={3} maxLength={5000} value={form.description} onChange={(e) => set("description", e.target.value)} />

        {form.workout == null && form.legacyTargets.length > 0 && (
          <div className="plan-form__legacy">
            <p className="plan-form__hint">{t("dialog.legacyHint")}</p>
            <ul className="plan-detail__targets" aria-label={t("detail.targets")}>
              {form.legacyTargets.map((target, index) => (
                <li key={index}>
                  {effortText(target, {
                    reps: (n, label) => t("detail.reps", { n, label }),
                    event: (key) => tr(`events.${key}`),
                    time: (ms) => formatRecordTime(ms, fmt),
                  })}
                </li>
              ))}
            </ul>
          </div>
        )}

        {form.workout != null && (
          <div className="plan-form__preview" aria-label={t("dialog.preview")}>
            {estimate.data && (
              <>
                <WorkoutTotals estimate={estimate.data} wattsWithoutFtp={ftp == null && hasWattTargets(form.workout)} />
                <IntensityChart segments={estimate.data.segments} />
              </>
            )}
            <WorkoutSteps steps={form.workout} gearLabels={kept && plan ? workoutGearLabels(plan) : undefined} />
          </div>
        )}

        {save.isError && (
          <p className="plan-form__error" role="alert">
            {errorMessage(save.error)}
          </p>
        )}
      </form>
    </Dialog>
  );
}
