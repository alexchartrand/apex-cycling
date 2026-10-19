import "./ProgressBar.css";

/** Horizontal meter; `value` is clamped to [0, max]. */
export function ProgressBar({
  value,
  max = 1,
  label,
  tone = "accent",
}: {
  value: number;
  max?: number;
  label: string;
  tone?: "accent" | "goal" | "positive";
}) {
  const clamped = Math.min(Math.max(value, 0), max);
  return (
    <div
      className={`progress progress--${tone}`}
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={clamped}
    >
      <div className="progress__fill" style={{ width: `${(clamped / max) * 100}%` }} />
    </div>
  );
}
