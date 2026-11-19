import { Milestone, Plus, Sparkles } from "lucide-react";
import { useTranslation } from "react-i18next";
import { ButtonLink, EmptyState, PageHeader, SkeletonGroup } from "../components/ui";
import { useAiAccess } from "../features/aicoach/useAiCoach";
import { useAthletePath } from "../features/athletes/athleteScope";
import { useActiveAthlete } from "../features/athletes/useActiveAthlete";
import { PlanCard } from "../features/trainingPlans/PlanCard";
import { useTrainingPlans } from "../features/trainingPlans/useTrainingPlans";
import "../features/trainingPlans/TrainingPlans.css";

/** The athlete's training plans, running and coming up first. A coach sees (and makes) them too. */
export function TrainingPlansPage() {
  const { t } = useTranslation(["trainingPlans", "common"]);
  const path = useAthletePath();
  const athleteId = useActiveAthlete().data?.id ?? "";
  const plans = useTrainingPlans(athleteId);
  const ai = useAiAccess(athleteId || undefined).data?.can_use ?? false;

  const all = plans.data ?? [];
  const current = all.filter((p) => p.state !== "finished").sort((a, b) => a.start_date.localeCompare(b.start_date));
  const finished = all.filter((p) => p.state === "finished");
  const actions = (
    <>
      {ai && (
        <ButtonLink to="/plans/new?ai=plans" variant="secondary" icon={<Sparkles aria-hidden />}>
          {t("askAiNew")}
        </ButtonLink>
      )}
      <ButtonLink to={path("/plans/new")} icon={<Plus aria-hidden />}>
        {t("new")}
      </ButtonLink>
    </>
  );

  return (
    <>
      <PageHeader title={t("title")} description={t("description")} actions={all.length > 0 ? actions : undefined} />
      {plans.isLoading && <SkeletonGroup lines={4} />}
      {plans.isError && <p role="alert">{t("common:loadError")}</p>}
      {plans.data && all.length === 0 && (
        <EmptyState icon={<Milestone aria-hidden />} title={t("empty")} description={t("emptyHint")} action={<div className="tplan-row">{actions}</div>} />
      )}
      {current.length > 0 && (
        <section className="tplan-group" aria-label={t("groups.current")}>
          <h2 className="tplan-group__title">{t("groups.current")}</h2>
          <div className="tplan-grid">
            {current.map((plan) => (
              <PlanCard key={plan.id} plan={plan} />
            ))}
          </div>
        </section>
      )}
      {finished.length > 0 && (
        <section className="tplan-group" aria-label={t("groups.finished")}>
          <h2 className="tplan-group__title">{t("groups.finished")}</h2>
          <div className="tplan-grid">
            {finished.map((plan) => (
              <PlanCard key={plan.id} plan={plan} />
            ))}
          </div>
        </section>
      )}
    </>
  );
}
