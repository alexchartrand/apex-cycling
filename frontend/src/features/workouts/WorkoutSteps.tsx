import { Repeat } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useFormat } from "../../i18n/useFormat";
import { formatRecordTime } from "../records/timeInput";
import { clockText } from "./profile";
import { isRepeat, type InnerRepeat, type WorkoutItem, type WorkoutStep } from "./types";

/** The step tree as read: a line per step, repeats as indented blocks. */
export function WorkoutSteps({ steps }: { steps: (WorkoutItem | InnerRepeat)[] }) {
  return (
    <ol className="workout-steps">
      {steps.map((item, index) => (
        <li key={index}>{isRepeat(item) ? <RepeatView block={item} /> : <StepView step={item} />}</li>
      ))}
    </ol>
  );
}

function RepeatView({ block }: { block: { count: number; steps: (WorkoutStep | InnerRepeat)[] } }) {
  const { t } = useTranslation("workouts");
  return (
    <div className="workout-steps__repeat">
      <span className="workout-steps__count">
        <Repeat aria-hidden />
        {t("steps.times", { count: block.count })}
      </span>
      <WorkoutSteps steps={block.steps} />
    </div>
  );
}

function StepView({ step }: { step: WorkoutStep }) {
  const { t } = useTranslation("workouts");
  const { t: tr } = useTranslation("records");
  const fmt = useFormat();
  const range = (low: number, high: number | null, digits = 0) =>
    high != null && high !== low ? `${fmt.number(low, digits)}–${fmt.number(high, digits)}` : fmt.number(low, digits);

  const length =
    step.duration_s != null
      ? clockText(step.duration_s)
      : step.distance_m != null
        ? fmt.distance(step.distance_m)
        : step.laps != null
          ? t("steps.laps", { count: step.laps })
          : step.event_key == null
            ? t("steps.open")
            : null;
  const track = step.event_key
    ? [tr(`events.${step.event_key}`), step.start_type ? tr(`startTypes.${step.start_type}`) : null].filter(Boolean).join(" · ")
    : null;
  const targets = [
    step.power ? `${range(step.power.low, step.power.high)} ${step.power.unit === "ftp_pct" ? t("units.ftpPct") : t("units.w")}` : null,
    step.cadence ? `${range(step.cadence.low, step.cadence.high)} ${t("units.rpm")}` : null,
    step.rpe != null ? t("steps.rpe", { value: step.rpe }) : null,
    step.target_time_ms != null ? formatRecordTime(step.target_time_ms, fmt) : null,
    step.gear ? `${step.gear.chainring_teeth}×${step.gear.cog_teeth}` : null,
  ].filter(Boolean);

  return (
    <div className={`workout-steps__step workout-steps__step--${step.kind}`}>
      <div className="workout-steps__head">
        <span className="workout-steps__label">{step.label ?? t(`kinds.${step.kind}`)}</span>
        {length && <span className="workout-steps__length">{length}</span>}
      </div>
      {(track || targets.length > 0) && <div className="workout-steps__targets">{[track, ...targets].filter(Boolean).join(" · ")}</div>}
      {step.notes && <p className="workout-steps__notes">{step.notes}</p>}
    </div>
  );
}
