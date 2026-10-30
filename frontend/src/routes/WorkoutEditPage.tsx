import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { errorMessage } from "../api/errors";
import { Button, Card, EmptyState, Input, PageHeader, Skeleton, Textarea, useToast } from "../components/ui";
import { useDebouncedValue } from "../hooks/useDebouncedValue";
import { useFormat } from "../i18n/useFormat";
import { IntensityChart } from "../features/workouts/IntensityChart";
import { hasWattTargets, type Workout } from "../features/workouts/types";
import { useEstimateFtp, useSaveWorkout, useWorkout, useWorkoutEstimate } from "../features/workouts/useWorkouts";
import { WorkoutEditor } from "../features/workouts/WorkoutEditor";
import { draftErrors, draftFrom, draftPayload, draftSteps, emptyDraft, LIMITS, type WorkoutDraft } from "../features/workouts/workoutDraft";
import { WorkoutTotals } from "../features/workouts/WorkoutTotals";
import "../features/workouts/Workouts.css";

/** `/workouts/new`, or `/workouts/:workoutId/edit` for one of my own. */
export function WorkoutEditPage() {
  const { t } = useTranslation("workouts");
  const { t: tc } = useTranslation("common");
  const { workoutId } = useParams();
  const workout = useWorkout(workoutId);

  if (workoutId == null) return <WorkoutForm workout={null} />;
  if (workout.data) {
    if (!workout.data.can_edit) return <Navigate to={`/workouts/${workoutId}`} replace />;
    return <WorkoutForm key={workout.data.id} workout={workout.data} />;
  }
  return (
    <>
      <PageHeader title={t("editTitle")} back={{ to: "/workouts", label: t("title") }} />
      {workout.isError ? <EmptyState compact title={tc("loadError")} /> : <Skeleton height="16rem" />}
    </>
  );
}

function WorkoutForm({ workout }: { workout: Workout | null }) {
  const { t } = useTranslation("workouts");
  const { t: tc } = useTranslation("common");
  const fmt = useFormat();
  const navigate = useNavigate();
  const { toast } = useToast();
  const save = useSaveWorkout();
  const ftp = useEstimateFtp();
  const [draft, setDraft] = useState<WorkoutDraft>(() => (workout ? draftFrom(workout, fmt) : emptyDraft()));
  const [showErrors, setShowErrors] = useState(false);
  const errors = draftErrors(draft);
  const set = <K extends keyof WorkoutDraft>(key: K, value: WorkoutDraft[K]) => setDraft((current) => ({ ...current, [key]: value }));

  // The chart follows the steps once they've stopped changing; a tree the
  // server would refuse keeps the last good chart.
  const steps = useDebouncedValue(draftSteps(draft), 400);
  const estimate = useWorkoutEstimate(steps, ftp);
  const leave = () => navigate(workout ? `/workouts/${workout.id}` : "/workouts");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const payload = draftPayload(draft);
    if (!payload) {
      setShowErrors(true);
      return;
    }
    try {
      const saved = await save.mutateAsync({ workoutId: workout?.id, payload });
      toast({ title: t("saved"), tone: "success" });
      navigate(`/workouts/${saved.id}`);
    } catch {
      // shown in the form
    }
  }

  return (
    <>
      <PageHeader
        title={workout ? t("editTitle") : t("newTitle")}
        back={workout ? { to: `/workouts/${workout.id}`, label: workout.name } : { to: "/workouts", label: t("title") }}
        actions={
          <>
            <Button variant="secondary" onClick={leave}>
              {tc("cancel")}
            </Button>
            <Button type="submit" form="workout-form" loading={save.isPending}>
              {tc("save")}
            </Button>
          </>
        }
      />
      <form id="workout-form" className="workout-edit" onSubmit={handleSubmit} noValidate>
        <div className="workout-edit__main">
          <Card>
            <div className="workout-edit__fields">
              <Input
                label={t("form.name")}
                value={draft.name}
                maxLength={120}
                placeholder={t("form.namePlaceholder")}
                error={showErrors && errors.name ? t("form.nameRequired") : undefined}
                onChange={(e) => set("name", e.target.value)}
                autoFocus={!workout}
              />
              <Input
                label={t("form.tags")}
                value={draft.tags}
                hint={t("form.tagsHint")}
                error={showErrors && errors.tags ? t("form.tagsInvalid", { max: LIMITS.tags, length: LIMITS.tagLength }) : undefined}
                onChange={(e) => set("tags", e.target.value)}
              />
              <Textarea label={t("form.description")} rows={3} maxLength={5000} value={draft.description} onChange={(e) => set("description", e.target.value)} />
            </div>
          </Card>
          <Card title={t("stepsTitle")}>
            {showErrors && errors.steps && (
              <p className="workout-editor__error" role="alert">
                {t(`form.steps.${errors.steps}`, { max: LIMITS.structureSize })}
              </p>
            )}
            <WorkoutEditor steps={draft.steps} onChange={(next) => set("steps", next)} errors={showErrors ? errors.nodes : null} />
          </Card>
          {save.isError && (
            <p className="workout-editor__error" role="alert">
              {errorMessage(save.error)}
            </p>
          )}
        </div>
        <aside className="workout-edit__preview">
          <Card title={t("profile")}>
            {estimate.data ? (
              <>
                <WorkoutTotals estimate={estimate.data} wattsWithoutFtp={ftp == null && steps != null && hasWattTargets(steps)} />
                <IntensityChart segments={estimate.data.segments} />
              </>
            ) : estimate.isError ? (
              <p className="workout-chart__empty">{errorMessage(estimate.error)}</p>
            ) : (
              <p className="workout-chart__empty">{t("chart.empty")}</p>
            )}
          </Card>
        </aside>
      </form>
    </>
  );
}
