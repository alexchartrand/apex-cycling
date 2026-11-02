import { CalendarPlus, Copy, Pencil, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router-dom";
import { errorMessage } from "../api/errors";
import { Badge, Button, ButtonLink, Card, ConfirmDialog, EmptyState, PageHeader, Skeleton, useToast } from "../components/ui";
import { localIsoDate } from "../i18n/format";
import { useActiveAthlete } from "../features/athletes/useActiveAthlete";
import { PlanDialog } from "../features/plan/PlanDialog";
import { downloadWorkout } from "../features/workouts/api";
import { DownloadMenu } from "../features/workouts/DownloadMenu";
import { IntensityChart } from "../features/workouts/IntensityChart";
import { WorkoutSteps } from "../features/workouts/WorkoutSteps";
import { hasWattTargets } from "../features/workouts/types";
import { WorkoutTotals } from "../features/workouts/WorkoutTotals";
import { useDeleteWorkout, useDuplicateWorkout, useEstimateFtp, useWorkout, useWorkoutEstimate } from "../features/workouts/useWorkouts";
import "../features/workouts/Workouts.css";

export function WorkoutPage() {
  const { t } = useTranslation("workouts");
  const { t: tc } = useTranslation("common");
  const { workoutId } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const workout = useWorkout(workoutId);
  // The library's own estimate has no FTP; with the athlete's, watt targets count too.
  const ftp = useEstimateFtp();
  const withFtp = useWorkoutEstimate(ftp != null && workout.data ? workout.data.steps : null, ftp);
  const duplicate = useDuplicateWorkout();
  const remove = useDeleteWorkout();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [scheduling, setScheduling] = useState(false);
  const athleteId = useActiveAthlete().data?.id;
  const back = { to: "/workouts", label: t("title") };

  if (!workout.data) {
    return (
      <>
        <PageHeader title={t("title")} back={back} />
        {workout.isError ? <EmptyState compact title={tc("loadError")} /> : <Skeleton height="16rem" />}
      </>
    );
  }
  const data = workout.data;
  const estimate = withFtp.data ?? data.estimate;

  async function handleDuplicate() {
    try {
      const copy = await duplicate.mutateAsync(data.id);
      toast({ title: t("duplicated"), tone: "success" });
      navigate(`/workouts/${copy.id}/edit`);
    } catch (error) {
      toast({ title: errorMessage(error), tone: "error" });
    }
  }

  return (
    <>
      <PageHeader
        title={data.name}
        back={back}
        eyebrow={data.source === "coach" && data.owner_name ? t("sourceBy", { name: data.owner_name }) : t(`sources.${data.source}`)}
        actions={
          <>
            {athleteId && (
              <Button icon={<CalendarPlus aria-hidden />} onClick={() => setScheduling(true)}>
                {t("schedule")}
              </Button>
            )}
            <Button variant="secondary" icon={<Copy aria-hidden />} loading={duplicate.isPending} onClick={handleDuplicate}>
              {t("duplicate")}
            </Button>
            <DownloadMenu download={(format) => downloadWorkout(data.id, format, athleteId)} />
            {data.can_edit && (
              <>
                <ButtonLink variant="secondary" to={`/workouts/${data.id}/edit`} icon={<Pencil aria-hidden />}>
                  {tc("edit")}
                </ButtonLink>
                <Button variant="ghost" icon={<Trash2 aria-hidden />} onClick={() => setConfirmDelete(true)}>
                  {tc("delete")}
                </Button>
              </>
            )}
          </>
        }
      />
      <div className="workout-page">
        {(data.description || data.tags.length > 0 || data.is_track) && (
          <div className="workout-page__intro">
            {data.description && <p className="workout-page__description">{data.description}</p>}
            <div className="workout-card__tags">
              {data.is_track && <Badge tone="highlight">{t("track")}</Badge>}
              {data.tags.map((tag) => (
                <Link key={tag} className="workout-tag" to={`/workouts?tag=${encodeURIComponent(tag)}`}>
                  #{tag}
                </Link>
              ))}
            </div>
          </div>
        )}
        <Card title={t("profile")}>
          <WorkoutTotals estimate={estimate} wattsWithoutFtp={ftp == null && hasWattTargets(data.steps)} />
          <IntensityChart segments={estimate.segments} />
        </Card>
        <Card title={t("stepsTitle")}>
          <WorkoutSteps steps={data.steps} />
        </Card>
      </div>
      {scheduling && athleteId && <PlanDialog key="schedule" athleteId={athleteId} date={localIsoDate()} plan={null} workout={data} onClose={() => setScheduling(false)} />}
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
            await remove.mutateAsync(data.id);
          } catch (error) {
            toast({ title: errorMessage(error), tone: "error" });
            throw error;
          }
          toast({ title: t("delete.done"), tone: "success" });
          navigate("/workouts");
        }}
      />
    </>
  );
}
