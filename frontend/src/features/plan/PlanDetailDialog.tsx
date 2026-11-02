import { Check, Dumbbell, Link2, Pencil, RotateCcw, SkipForward, Trash2, Unlink } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { errorMessage } from "../../api/errors";
import { Badge, Button, ConfirmDialog, Dialog, Select, useToast } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { formatRecordTime } from "../records/timeInput";
import { useSessions } from "../training/useTraining";
import { DownloadMenu } from "../workouts/DownloadMenu";
import { IntensityChart } from "../workouts/IntensityChart";
import { hasTrackEvents, hasWattTargets } from "../workouts/types";
import { WorkoutSteps } from "../workouts/WorkoutSteps";
import { useEstimateFtp } from "../workouts/useWorkouts";
import { WorkoutTotals } from "../workouts/WorkoutTotals";
import { downloadPlanWorkout } from "./api";
import { PlanDialog } from "./PlanDialog";
import { PlanResults } from "./PlanResults";
import { effortText, linkCandidates, STATUS_TONE, workoutGearLabels } from "./planForm";
import type { PlannedSession } from "./types";
import { useDeletePlan, usePlanAnswer } from "./usePlan";
import { useAthletePath } from "../athletes/athleteScope";
import "../workouts/Workouts.css";
import "./Plan.css";

/** One planned session: what is asked, and what the viewer may do about it. */
export function PlanDetailDialog({ athleteId, plan, onClose }: { athleteId: string; plan: PlannedSession; onClose: () => void }) {
  const path = useAthletePath();
  const { t } = useTranslation("plan");
  const { t: tr } = useTranslation("records");
  const { t: tc } = useTranslation("common");
  const fmt = useFormat();
  const { toast } = useToast();
  const sessions = useSessions(athleteId);
  const answer = usePlanAnswer(athleteId);
  const remove = useDeletePlan(athleteId);
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const candidates = linkCandidates(plan, sessions.data ?? []);
  const [picked, setPicked] = useState("");
  const chosen = picked || candidates[0]?.external_event_id || "";
  // The server's estimate used the FTP on the planned day; any FTP at all means watt steps count.
  const ftp = useEstimateFtp();
  const scored = plan.workout ? hasTrackEvents(plan.workout) : plan.targets.length > 0;

  async function run(action: Parameters<typeof answer.mutateAsync>[0]) {
    try {
      await answer.mutateAsync(action);
      toast({ title: t("answered"), tone: "success" });
      onClose();
    } catch (error) {
      toast({ title: errorMessage(error), tone: "error" });
    }
  }

  if (editing) return <PlanDialog athleteId={athleteId} date={plan.planned_date} plan={plan} onClose={onClose} />;

  return (
    <>
      <Dialog open size={plan.workout ? "lg" : "md"} onOpenChange={(open) => !open && onClose()} title={plan.title} description={`${fmt.date(plan.planned_date, "long")}${plan.created_by_name ? ` · ${t("by", { name: plan.created_by_name })}` : ""}`}>
        <div className="plan-detail">
          <p>
            <Badge tone={STATUS_TONE[plan.status]}>{t(`status.${plan.status}`)}</Badge>{" "}
            {plan.intervals && <Badge tone={plan.intervals === "failed" ? "negative" : "neutral"}>{t(`intervals.${plan.intervals}`)}</Badge>}
          </p>
          {plan.description && <p className="plan-detail__description">{plan.description}</p>}
          {plan.targets.length > 0 && (
            <ul className="plan-detail__targets" aria-label={t("detail.targets")}>
              {plan.targets.map((target, index) => (
                <li key={index}>
                  {effortText(target, {
                    reps: (n, label) => t("detail.reps", { n, label }),
                    event: (key) => tr(`events.${key}`),
                    time: (ms) => formatRecordTime(ms, fmt),
                  })}
                </li>
              ))}
            </ul>
          )}

          {plan.workout && (
            <section className="plan-detail__workout" aria-label={t("detail.workout")}>
              {plan.workout_estimate && (
                <>
                  <WorkoutTotals estimate={plan.workout_estimate} wattsWithoutFtp={ftp == null && hasWattTargets(plan.workout)} />
                  <IntensityChart segments={plan.workout_estimate.segments} />
                </>
              )}
              <WorkoutSteps steps={plan.workout} gearLabels={workoutGearLabels(plan)} />
              <div className="plan-detail__workout-actions">
                <DownloadMenu download={(format) => downloadPlanWorkout(athleteId, plan.id, format)} />
                {plan.source_workout_id && (
                  <Link className="plan-detail__source" to={`/workouts/${plan.source_workout_id}`} onClick={onClose}>
                    <Dumbbell aria-hidden /> {t("detail.openSource")}
                  </Link>
                )}
              </div>
            </section>
          )}

          {plan.session && (
            <p>
              {t("detail.linkedTo")}{" "}
              <Link to={path(`/sessions/${plan.session.external_event_id}`)} onClick={onClose}>
                {plan.session.event_name} · {fmt.date(plan.session.event_date, "medium")}
              </Link>
            </p>
          )}

          {plan.session && scored && (
            <PlanResults athleteId={athleteId} planId={plan.id} eventId={plan.session.external_event_id} />
          )}

          {plan.can_mark && plan.status === "planned" && (
            <div className="plan-detail__answer">
              {candidates.length > 0 ? (
                <div className="plan-detail__link">
                  <Select label={t("detail.linkLabel")} value={chosen} onChange={(e) => setPicked(e.target.value)}>
                    {candidates.map((session) => (
                      <option key={session.external_event_id} value={session.external_event_id}>
                        {session.event_name} · {fmt.date(session.event_date, "weekday")}
                      </option>
                    ))}
                  </Select>
                  <Button icon={<Link2 aria-hidden />} loading={answer.isPending} onClick={() => void run({ planId: plan.id, link: chosen })}>
                    {t("detail.link")}
                  </Button>
                </div>
              ) : (
                <p className="plan-detail__hint">{t("detail.noSessionNear")}</p>
              )}
              <div className="plan-detail__buttons">
                <Button variant="secondary" icon={<Check aria-hidden />} onClick={() => void run({ planId: plan.id, status: "done" })}>
                  {t("detail.markDone")}
                </Button>
                <Button variant="secondary" icon={<SkipForward aria-hidden />} onClick={() => void run({ planId: plan.id, status: "skipped" })}>
                  {t("detail.skip")}
                </Button>
              </div>
            </div>
          )}
          {plan.can_mark && plan.status !== "planned" && (
            <div className="plan-detail__buttons">
              {plan.session ? (
                <Button variant="secondary" icon={<Unlink aria-hidden />} onClick={() => void run({ planId: plan.id, unlink: true })}>
                  {t("detail.unlink")}
                </Button>
              ) : (
                <Button variant="secondary" icon={<RotateCcw aria-hidden />} onClick={() => void run({ planId: plan.id, status: "planned" })}>
                  {t("detail.reopen")}
                </Button>
              )}
            </div>
          )}

          {plan.can_edit && (
            <div className="plan-detail__buttons plan-detail__buttons--end">
              <Button variant="ghost" icon={<Pencil aria-hidden />} onClick={() => setEditing(true)}>
                {t("detail.edit")}
              </Button>
              <Button variant="ghost" icon={<Trash2 aria-hidden />} onClick={() => setConfirmDelete(true)}>
                {tc("delete")}
              </Button>
            </div>
          )}
        </div>
      </Dialog>
      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={t("delete.title")}
        description={t("delete.body")}
        confirmLabel={tc("delete")}
        cancelLabel={tc("cancel")}
        tone="danger"
        onConfirm={async () => {
          try {
            await remove.mutateAsync(plan.id);
            toast({ title: t("delete.done"), tone: "success" });
            onClose();
          } catch (error) {
            toast({ title: errorMessage(error), tone: "error" });
            throw error;
          }
        }}
      />
    </>
  );
}
