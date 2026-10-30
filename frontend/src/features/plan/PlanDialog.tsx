import { ListPlus, Wand2, X } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import { errorMessage } from "../../api/errors";
import { Button, Dialog, Input, Select, Textarea, useToast } from "../../components/ui";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import { useFormat } from "../../i18n/useFormat";
import { useBikes } from "../equipment/useEquipment";
import { formatRecordTime } from "../records/timeInput";
import { getWorkout } from "../workouts/api";
import { IntensityChart } from "../workouts/IntensityChart";
import { hasWattTargets, type Workout, type WorkoutSource } from "../workouts/types";
import { useEstimateFtp, useWorkoutEstimate, useWorkouts } from "../workouts/useWorkouts";
import { WorkoutEditor } from "../workouts/WorkoutEditor";
import { emptyDraft, LIMITS } from "../workouts/workoutDraft";
import { WorkoutTotals } from "../workouts/WorkoutTotals";
import { effortText, emptyPlanForm, planFormErrors, planFormFrom, planPayload, planSteps, targetsToSteps, withLibraryWorkout, type PlanForm } from "./planForm";
import type { PlannedSession } from "./types";
import { useSavePlan } from "./usePlan";
import "../workouts/Workouts.css";
import "./Plan.css";

const SOURCES: WorkoutSource[] = ["mine", "coach", "preset"];

/**
 * Plan a session on `date`, or edit `plan`; `workout` starts a new plan from
 * that library workout. The plan keeps its own copy of the steps, so they can
 * be adapted here without touching the library. Remount it (key) per plan so
 * its fields start fresh.
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
  const bikes = useBikes(athleteId).data ?? [];
  const library = useWorkouts({});
  const ftp = useEstimateFtp();
  const [form, setForm] = useState<PlanForm>(() => {
    if (plan) return planFormFrom(plan, fmt);
    const empty = emptyPlanForm(date);
    return workout ? withLibraryWorkout(empty, workout, fmt) : empty;
  });
  const [picking, setPicking] = useState(false);
  const [showErrors, setShowErrors] = useState(false);
  const errors = planFormErrors(form);
  const set = <K extends keyof PlanForm>(key: K, value: PlanForm[K]) => setForm((current) => ({ ...current, [key]: value }));

  const steps = useDebouncedValue(planSteps(form), 400);
  const estimate = useWorkoutEstimate(steps, ftp);

  async function pickWorkout(workoutId: string) {
    if (!workoutId) return;
    setPicking(true);
    try {
      const picked = await queryClient.fetchQuery({ queryKey: ["workout", workoutId], queryFn: () => getWorkout(workoutId) });
      setForm((current) => withLibraryWorkout(current, picked, fmt));
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

  const gears = bikes.flatMap((bike) => bike.gears);
  const workouts = library.data ?? [];

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
        <div className="plan-form__row plan-form__row--title">
          <Input
            label={t("dialog.title")}
            value={form.title}
            maxLength={120}
            placeholder={t("dialog.titlePlaceholder")}
            error={showErrors && errors.title ? t("dialog.titleRequired") : undefined}
            onChange={(e) => set("title", e.target.value)}
            autoFocus={!plan && !workout}
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

        <fieldset className="plan-form__workout">
          <legend>{t("dialog.workout")}</legend>
          <div className="plan-form__library">
            <Select
              label={form.steps ? t("dialog.replaceFromLibrary") : t("dialog.fromLibrary")}
              value=""
              disabled={picking || library.isLoading}
              onChange={(e) => void pickWorkout(e.target.value)}
            >
              <option value="">{t("dialog.pickWorkout")}</option>
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
            </Select>
            {form.steps == null && form.legacyTargets.length === 0 && (
              <Button size="sm" variant="secondary" icon={<ListPlus aria-hidden />} onClick={() => set("steps", emptyDraft().steps)}>
                {t("dialog.buildSteps")}
              </Button>
            )}
            {form.steps != null && (
              <Button size="sm" variant="ghost" icon={<X aria-hidden />} onClick={() => setForm((current) => ({ ...current, steps: null, sourceWorkoutId: null }))}>
                {t("dialog.removeWorkout")}
              </Button>
            )}
          </div>
          <p className="plan-form__hint">{form.steps && form.sourceWorkoutId ? t("dialog.copiedHint") : t("dialog.workoutHint")}</p>

          {form.steps == null && form.legacyTargets.length > 0 && (
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
              <Button
                size="sm"
                variant="secondary"
                icon={<Wand2 aria-hidden />}
                onClick={() => setForm((current) => ({ ...current, steps: targetsToSteps(current.legacyTargets, gears, fmt), legacyTargets: [] }))}
              >
                {t("dialog.convertTargets")}
              </Button>
            </div>
          )}

          {form.steps != null && (
            <div className="plan-form__editor">
              {showErrors && errors.steps && (
                <p className="workout-editor__error" role="alert">
                  {tw(`form.steps.${errors.steps}`, { max: LIMITS.structureSize })}
                </p>
              )}
              <WorkoutEditor steps={form.steps} onChange={(next) => set("steps", next)} errors={showErrors ? errors.nodes : null} />
              {estimate.data && (
                <div className="plan-form__preview">
                  <WorkoutTotals estimate={estimate.data} wattsWithoutFtp={ftp == null && steps != null && hasWattTargets(steps)} />
                  <IntensityChart segments={estimate.data.segments} />
                </div>
              )}
            </div>
          )}
        </fieldset>

        {save.isError && (
          <p className="plan-form__error" role="alert">
            {errorMessage(save.error)}
          </p>
        )}
      </form>
    </Dialog>
  );
}
