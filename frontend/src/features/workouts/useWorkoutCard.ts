import { useTranslation } from "react-i18next";
import { useFormat } from "../../i18n/useFormat";
import { useRecords } from "../records/useRecords";
import { renderPng, shareImage, type ShareOutcome } from "../share/renderShareCard";
import { useEstimateFtp } from "./useWorkouts";
import { bestTimes, CARD_LAYOUTS, drawWorkoutCard, workoutCardFileName, workoutCardModel, type WorkoutCardInput, type WorkoutCardSize, type WorkoutCardTexts } from "./workoutCard";

export type WorkoutCardSource = Omit<WorkoutCardInput, "ftpW" | "bests">;

/**
 * Makes the workout card for the active athlete: watts from their current FTP
 * (a plan's own estimate used the FTP on its day, which is the same unless it
 * changed since) and a track step's time from their records board.
 */
export function useWorkoutCard(athleteId: string | undefined) {
  const { t } = useTranslation("workouts");
  const { t: tr } = useTranslation("records");
  const fmt = useFormat();
  const ftpW = useEstimateFtp();
  const records = useRecords(athleteId ?? "");

  const texts: WorkoutCardTexts = {
    brand: t("card.brand"),
    kind: (kind) => t(`kinds.${kind}`),
    repeat: (count) => t("steps.times", { count }),
    laps: (count) => t("steps.laps", { count }),
    open: t("card.open"),
    event: (key) => tr(`events.${key}`),
    start: (start) => tr(`startTypes.${start}`),
    rpe: (value) => t("steps.rpe", { value }),
    best: (time) => t("card.best", { time }),
    tss: (value) => t("tssValue", { value }),
    ftp: (watts) => t("card.ftp", { watts }),
    noFtp: t("card.noFtp"),
    units: { ftpPct: t("units.ftpPct"), w: t("units.w"), rpm: t("units.rpm") },
  };

  return async function makeCard(source: WorkoutCardSource, size: WorkoutCardSize): Promise<ShareOutcome> {
    const model = workoutCardModel({ ...source, ftpW, bests: bestTimes(records.data ?? []) }, texts, fmt);
    const layout = CARD_LAYOUTS[size];
    const blob = await renderPng(layout.width, layout.height, (ctx) => drawWorkoutCard(ctx, model, size, (count) => t("card.more", { count })));
    return shareImage(blob, workoutCardFileName(source.name, size), source.name);
  };
}
