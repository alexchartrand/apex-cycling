import { useEffect, useState, type FormEvent } from "react";
import { Plus, Sparkles, Trash2, Wand2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { errorMessage } from "../api/errors";
import { Button, Card, IconButton, Input, PageHeader, Select, SkeletonGroup, Textarea, useToast } from "../components/ui";
import { localIsoDate } from "../i18n/format";
import { useFormat } from "../i18n/useFormat";
import { useAthletePath } from "../features/athletes/athleteScope";
import { useActiveAthlete } from "../features/athletes/useActiveAthlete";
import { useGoals } from "../features/goals/useGoals";
import { formatRecordTime } from "../features/records/timeInput";
import type { StandardEventKey } from "../features/records/types";
import { useCompetitions } from "../features/season/useSeason";
import {
  addedPhase,
  draftErrors,
  draftFrom,
  draftPayload,
  emptyDraft,
  phaseDraft,
  withRace,
  type PhaseDraft,
  type PlanDraft,
} from "../features/trainingPlans/planDraft";
import { PHASE_KINDS, SPORTS, type PhaseKind, type Sport } from "../features/trainingPlans/types";
import { useSaveTrainingPlan, useSuggestPhases, useTrainingPlan } from "../features/trainingPlans/useTrainingPlans";
import "../features/trainingPlans/TrainingPlans.css";

/**
 * `/plans/new` and `/plans/:planId/edit`: the plan's goal, dates, race and phases.
 * `/plans/new?ai=plans|chat` is the first step of "build it with the AI coach": the same
 * questions without the phases (suggested on save), then the AI coach's intake on the
 * saved plan, which keeps its sport, goal and dates. `ai` says where "back" goes.
 */
export function TrainingPlanEditPage() {
  const { t } = useTranslation(["trainingPlans", "common"]);
  const { t: ta } = useTranslation("activities");
  const { t: tr } = useTranslation("records");
  const { t: ti } = useTranslation("aicoach");
  const { planId } = useParams();
  const [params] = useSearchParams();
  const aiFrom = planId ? null : params.get("ai");
  const ai = aiFrom !== null;
  const fmt = useFormat();
  const path = useAthletePath();
  const navigate = useNavigate();
  const { toast } = useToast();
  const athleteId = useActiveAthlete().data?.id ?? "";
  const existing = useTrainingPlan(athleteId, planId);
  const races = useCompetitions(athleteId);
  const goals = useGoals(athleteId);
  const save = useSaveTrainingPlan(athleteId);
  const suggest = useSuggestPhases(athleteId);
  const [draft, setDraft] = useState<PlanDraft | null>(planId ? null : emptyDraft(localIsoDate()));
  const [showErrors, setShowErrors] = useState(false);

  useEffect(() => {
    if (planId && existing.data && draft === null) setDraft(draftFrom(existing.data));
  }, [planId, existing.data, draft]);

  if (!draft) return existing.isError ? <p role="alert">{t("common:loadError")}</p> : <SkeletonGroup lines={6} />;
  const errors = draftErrors(draft);
  const set = <K extends keyof PlanDraft>(field: K, value: PlanDraft[K]) => setDraft({ ...draft, [field]: value });
  const setPhase = (index: number, changes: Partial<PhaseDraft>) =>
    set("phases", draft.phases.map((phase, i) => (i === index ? { ...phase, ...changes } : phase)));
  const raceList = (races.data ?? []).filter((race) => race.days_until >= 0 || race.id === draft.raceId);
  const goalList = (goals.data ?? []).filter((goal) => goal.target_date >= draft.start || goal.id === draft.goalId);
  const back = planId ? path(`/plans/${planId}`) : aiFrom === "chat" ? "/ai-coach?tab=chat" : path("/plans");

  function suggestedPhases(of: PlanDraft) {
    const race = raceList.find((r) => r.id === of.raceId);
    return suggest.mutateAsync({
      start_date: of.start,
      end_date: of.end,
      race_priority: race && race.competition_date === of.end ? race.priority : null,
    });
  }

  async function suggestPhases() {
    try {
      const phases = await suggestedPhases(draft!);
      setDraft((current) => (current ? { ...current, phases: phases.map(phaseDraft) } : current));
    } catch (error) {
      toast({ title: errorMessage(error), tone: "error" });
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    let payload = draftPayload(draft!);
    if (!payload) {
      setShowErrors(true);
      return;
    }
    if (ai && payload.phases.length === 0) {
      // The AI coach details the sessions and the outline, never an existing plan's phases.
      try {
        payload = draftPayload({ ...draft!, phases: (await suggestedPhases(draft!)).map(phaseDraft) }) ?? payload;
      } catch {
        // a plan without phases is still a plan
      }
    }
    try {
      const saved = await save.mutateAsync({ planId, payload });
      if (ai) {
        navigate(`/ai-coach?tab=chat&build=${saved.id}`);
        return;
      }
      toast({ title: t("builder.saved"), tone: "success" });
      navigate(path(`/plans/${saved.id}`));
    } catch {
      // shown below the form
    }
  }

  return (
    <>
      <PageHeader
        title={planId ? t("builder.editTitle") : ai ? t("builder.aiTitle") : t("builder.newTitle")}
        description={ai ? t("builder.aiDescription") : t("builder.description")}
        back={{ to: back, label: planId ? (existing.data?.name ?? t("back")) : aiFrom === "chat" ? ti("title") : t("back") }}
      />
      <form className="tplan-form" onSubmit={onSubmit} noValidate>
        <Card as="section">
          <div className="tplan-form__grid">
            <Input
              label={t("builder.name")}
              value={draft.name}
              maxLength={120}
              placeholder={t("builder.namePlaceholder")}
              error={showErrors && errors.name ? t("errors.name") : undefined}
              onChange={(e) => set("name", e.target.value)}
              autoFocus={!planId}
            />
            <Select label={t("builder.sport")} value={draft.sport} onChange={(e) => set("sport", e.target.value as Sport)}>
              {SPORTS.map((sport) => (
                <option key={sport} value={sport}>
                  {ta(`types.${sport}.name`)}
                </option>
              ))}
            </Select>
            <Input
              label={t("builder.start")}
              type="date"
              value={draft.start}
              error={showErrors && errors.dates ? t("errors.dates") : undefined}
              onChange={(e) => set("start", e.target.value)}
            />
            <Input label={t("builder.end")} type="date" value={draft.end} onChange={(e) => set("end", e.target.value)} />
          </div>
          <Textarea
            label={t("builder.goalText")}
            value={draft.goalText}
            rows={2}
            maxLength={500}
            placeholder={t("builder.goalPlaceholder")}
            onChange={(e) => set("goalText", e.target.value)}
          />
          <div className="tplan-form__grid">
            <Input
              label={t("builder.goalDate")}
              type="date"
              value={draft.goalDate}
              error={showErrors && errors.goalDate ? t("errors.goalDate") : undefined}
              onChange={(e) => set("goalDate", e.target.value)}
            />
            <Input label={t("builder.hours")} inputMode="decimal" value={draft.hours} onChange={(e) => set("hours", e.target.value)} />
            <Select
              label={t("builder.race")}
              value={draft.raceId}
              hint={t("builder.raceHint")}
              onChange={(e) => {
                const race = raceList.find((r) => r.id === e.target.value);
                setDraft(withRace(draft, e.target.value, race?.competition_date ?? null));
              }}
            >
              <option value="">{t("builder.noRace")}</option>
              {raceList.map((race) => (
                <option key={race.id} value={race.id}>
                  {race.name} · {fmt.date(race.competition_date, "dayMonth")} · {race.priority}
                </option>
              ))}
            </Select>
            {draft.sport === "track_cycling" && (
              <Select label={t("builder.timeGoal")} value={draft.goalId} hint={t("builder.timeGoalHint")} onChange={(e) => set("goalId", e.target.value)}>
                <option value="">{t("builder.noTimeGoal")}</option>
                {goalList.map((goal) => (
                  <option key={goal.id} value={goal.id}>
                    {tr(`events.${goal.event_key as StandardEventKey}`)} {tr(`startTypes.${goal.start_type}`)} ·{" "}
                    {formatRecordTime(goal.target_time_ms, fmt)} · {fmt.date(goal.target_date, "dayMonth")}
                  </option>
                ))}
              </Select>
            )}
          </div>
        </Card>

        {!ai && (
        <Card
          as="section"
          title={t("builder.phases")}
          actions={
            <Button type="button" size="sm" variant="secondary" icon={<Wand2 aria-hidden />} loading={suggest.isPending} disabled={!!errors.dates} onClick={() => void suggestPhases()}>
              {t("builder.suggest")}
            </Button>
          }
        >
          <p className="ui-card__hint">{t("builder.suggestHint")}</p>
          {draft.phases.length > 0 && (
            <ol className="tplan-form__phases">
              {draft.phases.map((phase, index) => (
                <li key={index} className="tplan-form__phase">
                  <Select label={t("builder.phaseKind")} value={phase.kind} onChange={(e) => setPhase(index, { kind: e.target.value as PhaseKind })}>
                    {PHASE_KINDS.map((kind) => (
                      <option key={kind} value={kind}>
                        {t(`phase.kinds.${kind}`)}
                      </option>
                    ))}
                  </Select>
                  <Input label={t("builder.phaseStart")} type="date" value={phase.start} onChange={(e) => setPhase(index, { start: e.target.value })} />
                  <Input label={t("builder.phaseEnd")} type="date" value={phase.end} onChange={(e) => setPhase(index, { end: e.target.value })} />
                  <Input label={t("builder.phaseHours")} inputMode="decimal" value={phase.hours} onChange={(e) => setPhase(index, { hours: e.target.value })} />
                  <Input label={t("builder.phaseName")} value={phase.name} maxLength={60} onChange={(e) => setPhase(index, { name: e.target.value })} />
                  <Input label={t("builder.phaseFocus")} value={phase.focus} maxLength={300} onChange={(e) => setPhase(index, { focus: e.target.value })} />
                  <IconButton
                    type="button"
                    aria-label={t("builder.removePhase")}
                    onClick={() => set("phases", draft.phases.filter((_, i) => i !== index))}
                  >
                    <Trash2 aria-hidden />
                  </IconButton>
                </li>
              ))}
            </ol>
          )}
          {showErrors && errors.phases && (
            <p className="tplan-error" role="alert">
              {t(`errors.${errors.phases}`)}
            </p>
          )}
          <Button
            type="button"
            size="sm"
            variant="ghost"
            icon={<Plus aria-hidden />}
            disabled={!!errors.dates || draft.phases.length >= 20}
            onClick={() => set("phases", [...draft.phases, addedPhase(draft)])}
          >
            {t("builder.addPhase")}
          </Button>
        </Card>
        )}

        <div className="tplan-row">
          <Button type="submit" loading={save.isPending || suggest.isPending} icon={ai ? <Sparkles aria-hidden /> : undefined}>
            {ai ? t("builder.aiSave") : t("builder.save")}
          </Button>
          <Button type="button" variant="ghost" onClick={() => navigate(back)}>
            {t("common:cancel")}
          </Button>
          {save.isError && (
            <span className="tplan-error" role="alert">
              {errorMessage(save.error)}
            </span>
          )}
        </div>
      </form>
    </>
  );
}
