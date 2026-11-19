import { useTranslation } from "react-i18next";
import type { TrainingPlan } from "./types";

/** Who wrote the plan, as the list and the detail page say it. */
export function useAuthorText() {
  const { t } = useTranslation("trainingPlans");
  return (plan: Pick<TrainingPlan, "author" | "created_by_name">) =>
    plan.author === "coach" && plan.created_by_name ? t("author.named", { name: plan.created_by_name }) : t(`author.${plan.author}`);
}
