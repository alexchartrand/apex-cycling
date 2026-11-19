import { useState } from "react";
import { CalendarPlus, Milestone, Pencil, Sparkles, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { errorMessage } from "../api/errors";
import { Badge, Button, ButtonLink, Card, ConfirmDialog, EmptyState, PageHeader, SkeletonGroup, useToast } from "../components/ui";
import { localIsoDate } from "../i18n/format";
import { useFormat } from "../i18n/useFormat";
import { TypeBadge } from "../features/activities/TypeBadge";
import { useAiAccess } from "../features/aicoach/useAiCoach";
import { useAthletePath } from "../features/athletes/athleteScope";
import { useActiveAthlete } from "../features/athletes/useActiveAthlete";
import { PlanDetailDialog } from "../features/plan/PlanDetailDialog";
import { PlanDialog } from "../features/plan/PlanDialog";
import { STATUS_TONE } from "../features/plan/planForm";
import type { PlannedSession } from "../features/plan/types";
import { formatRecordTime } from "../features/records/timeInput";
import type { StandardEventKey } from "../features/records/types";
import { useAuthorText } from "../features/trainingPlans/useAuthorText";
import { PhaseTimeline } from "../features/trainingPlans/PhaseTimeline";
import { phaseColor } from "../features/trainingPlans/phases";
import { PlanProgressCard } from "../features/trainingPlans/PlanProgressCard";
import { useDeleteTrainingPlan, usePlanSessions, useTrainingPlan } from "../features/trainingPlans/useTrainingPlans";
import { lengthText } from "../features/workouts/profile";
import "../features/plan/Plan.css";
import "../features/trainingPlans/TrainingPlans.css";

/** One training plan: its goal, phases, progress, week outline and sessions. */
export function TrainingPlanPage() {
  const { t } = useTranslation(["trainingPlans", "common"]);
  const { t: tr } = useTranslation("records");
  const { planId = "" } = useParams();
  const fmt = useFormat();
  const path = useAthletePath();
  const navigate = useNavigate();
  const { toast } = useToast();
  const athleteId = useActiveAthlete().data?.id ?? "";
  const plan = useTrainingPlan(athleteId, planId);
  const sessions = usePlanSessions(athleteId, planId);
  const remove = useDeleteTrainingPlan(athleteId);
  const ai = useAiAccess(athleteId || undefined).data?.can_use ?? false;
  const authorText = useAuthorText();
  const [open, setOpen] = useState<PlannedSession | null>(null);
  const [adding, setAdding] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const back = { to: path("/plans"), label: t("back") };

  if (plan.error instanceof ApiError && plan.error.status === 404) {
    return (
      <EmptyState
        icon={<Milestone aria-hidden />}
        title={t("notFound")}
        action={<ButtonLink to={back.to}>{t("back")}</ButtonLink>}
      />
    );
  }
  if (!plan.data) return plan.isError ? <p role="alert">{t("common:loadError")}</p> : <SkeletonGroup lines={6} />;
  const data = plan.data;
  const today = localIsoDate();
  const list = sessions.data ?? [];
  const firstDay = data.start_date > today ? data.start_date : today <= data.end_date ? today : data.start_date;

  const actions = (
    <>
      {ai && data.author !== "coach" && (
        <ButtonLink to={`/ai-coach?tab=chat&build=${data.id}`} variant="secondary" icon={<Sparkles aria-hidden />}>
          {t("actions.askAi")}
        </ButtonLink>
      )}
      <Button variant="secondary" icon={<CalendarPlus aria-hidden />} onClick={() => setAdding(true)}>
        {t("sessions.schedule")}
      </Button>
      {data.can_edit && (
        <>
          <ButtonLink to={path(`/plans/${data.id}/edit`)} variant="secondary" icon={<Pencil aria-hidden />}>
            {t("actions.edit")}
          </ButtonLink>
          <Button variant="danger" icon={<Trash2 aria-hidden />} onClick={() => setConfirmDelete(true)}>
            {t("actions.delete")}
          </Button>
        </>
      )}
    </>
  );

  return (
    <>
      <PageHeader title={data.name} description={data.goal_text ?? undefined} back={back} actions={actions} />
      <div className="tplan-page">
        <Card as="section">
          <dl className="tplan-facts">
            <div>
              <dt>{t("builder.sport")}</dt>
              <dd>
                <TypeBadge type={data.sport} />
              </dd>
            </div>
            <div>
              <dt>{t("dates")}</dt>
              <dd>
                {t("range", { start: fmt.date(data.start_date, "medium"), end: fmt.date(data.end_date, "medium") })}
              </dd>
            </div>
            {data.goal_date && (
              <div>
                <dt>{t("goal")}</dt>
                <dd>{t("goalBy", { date: fmt.date(data.goal_date, "medium") })}</dd>
              </div>
            )}
            {data.race && (
              <div>
                <dt>{t("race")}</dt>
                <dd>
                  {data.race.name} · {fmt.date(data.race.date, "medium")} · {data.race.priority}
                </dd>
              </div>
            )}
            {data.goal && (
              <div>
                <dt>{t("timeGoal")}</dt>
                <dd>
                  {t("timeGoalValue", {
                    event: tr(`events.${data.goal.event_key as StandardEventKey}`),
                    start: tr(`startTypes.${data.goal.start_type}`),
                    time: formatRecordTime(data.goal.target_time_ms, fmt),
                  })}
                </dd>
              </div>
            )}
            {data.hours_per_week != null && (
              <div>
                <dt>{t("builder.hours")}</dt>
                <dd>{t("hoursPerWeek", { value: fmt.number(data.hours_per_week, 1) })}</dd>
              </div>
            )}
            <div>
              <dt>{t("statusLabel")}</dt>
              <dd>
                {data.state === "upcoming"
                  ? t("state.upcoming", { date: fmt.date(data.start_date, "dayMonth") })
                  : t(`state.${data.state}`)}{" "}
                · <span className="tplan-muted">{authorText(data)}</span>
              </dd>
            </div>
          </dl>
        </Card>

        <Card as="section" title={t("phase.timeline")}>
          {data.phases.length === 0 ? (
            <p className="ui-card__hint">{t("phase.none")}</p>
          ) : (
            <>
              <PhaseTimeline plan={data} />
              <ol className="tplan-phases">
                {data.phases.map((phase, index) => (
                  <li key={index} className={index === data.current_phase ? "tplan-phase tplan-phase--current" : "tplan-phase"}>
                    <span className="tplan-phase__dot" style={{ background: phaseColor(phase.kind) }} aria-hidden />
                    <strong>{phase.name || t(`phase.kinds.${phase.kind}`)}</strong>
                    <span className="tplan-muted">
                      {t("range", { start: fmt.date(phase.start, "dayMonth"), end: fmt.date(phase.end, "dayMonth") })}
                    </span>
                    {phase.hours != null && <span className="tplan-muted">{t("hoursPerWeek", { value: fmt.number(phase.hours, 1) })}</span>}
                    {phase.focus && <span className="tplan-phase__focus">{phase.focus}</span>}
                  </li>
                ))}
              </ol>
            </>
          )}
        </Card>

        <PlanProgressCard progress={data.progress} />

        {data.weeks.length > 0 && (
          <Card as="section" title={t("outline.title")}>
            <ol className="tplan-weeks">
              {data.weeks.map((week) => (
                <li key={week.week_start}>
                  <strong>{t("outline.weekOf", { date: fmt.date(week.week_start, "dayMonth") })}</strong> · {week.focus}
                  {week.hours != null && <> · {t("hoursPerWeek", { value: fmt.number(week.hours, 1) })}</>}
                  {week.notes && <div className="tplan-muted">{week.notes}</div>}
                </li>
              ))}
            </ol>
          </Card>
        )}

        <Card as="section" title={t("sessions.title")}>
          {sessions.isLoading && <SkeletonGroup lines={3} />}
          {sessions.data && list.length === 0 && <p className="ui-card__hint">{t("sessions.empty")}</p>}
          {list.length > 0 && (
            <ul className="tplan-sessions">
              {list.map((session) => {
                const missed = session.status === "planned" && session.planned_date < today;
                return (
                  <li key={session.id}>
                    <button type="button" className="tplan-session" onClick={() => setOpen(session)}>
                      <span className="tplan-session__date">{fmt.date(session.planned_date, "weekday")}</span>
                      <span className="tplan-session__title">{session.title}</span>
                      {session.workout_estimate && <span className="tplan-muted">{lengthText(session.workout_estimate.duration_s)}</span>}
                      <Badge tone={missed ? "marker" : STATUS_TONE[session.status]}>
                        {missed ? t("sessions.missed") : t(`sessions.status.${session.status}`)}
                      </Badge>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      </div>

      {open && <PlanDetailDialog key={open.id} athleteId={athleteId} plan={open} onClose={() => setOpen(null)} />}
      {adding && <PlanDialog athleteId={athleteId} date={firstDay} plan={null} trainingPlanId={data.id} onClose={() => setAdding(false)} />}
      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={t("actions.deleteTitle", { name: data.name })}
        description={
          data.progress.upcoming > 0 ? t("actions.deleteHint", { count: data.progress.upcoming }) : t("actions.deleteHintNone")
        }
        confirmLabel={t("actions.delete")}
        cancelLabel={t("common:cancel")}
        tone="danger"
        onConfirm={async () => {
          try {
            await remove.mutateAsync(data.id);
            toast({ title: t("actions.deleted"), tone: "success" });
            navigate(back.to);
          } catch (error) {
            toast({ title: errorMessage(error), tone: "error" });
            throw error;
          }
        }}
      />
    </>
  );
}
