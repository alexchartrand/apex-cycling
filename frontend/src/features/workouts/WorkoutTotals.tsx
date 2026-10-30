import { useTranslation } from "react-i18next";
import { StatTile } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { lengthText } from "./profile";
import type { WorkoutEstimate } from "./types";

/** Estimated duration and TSS, with what they leave out. */
export function WorkoutTotals({ estimate, wattsWithoutFtp }: { estimate: WorkoutEstimate; wattsWithoutFtp: boolean }) {
  const { t } = useTranslation("workouts");
  const fmt = useFormat();
  const notes = [
    estimate.open_steps > 0 ? t("totals.openSteps", { count: estimate.open_steps }) : null,
    estimate.unrated_s > 0 ? t("totals.unrated", { duration: lengthText(estimate.unrated_s) }) : null,
    wattsWithoutFtp ? t("totals.noFtp") : null,
  ].filter(Boolean);
  return (
    <div className="workout-totals">
      <div className="workout-totals__tiles">
        <StatTile label={t("totals.duration")} value={lengthText(estimate.duration_s)} />
        <StatTile label={t("totals.tss")} value={estimate.tss != null ? fmt.number(estimate.tss, 0) : "—"} />
      </div>
      {notes.length > 0 && <p className="workout-totals__notes">{notes.join(" ")}</p>}
      <p className="workout-totals__notes">{t("totals.estimateHint")}</p>
    </div>
  );
}
