import type { ReactNode } from "react";
import "./SegmentedControl.css";

export type SegmentOption<T extends string> = { value: T; label: ReactNode; icon?: ReactNode };

/** A compact radio group rendered as joined pills (theme, units, chart ranges…). */
export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  "aria-label": ariaLabel,
  size = "md",
}: {
  options: SegmentOption<T>[];
  value: T;
  onChange: (value: T) => void;
  "aria-label": string;
  size?: "sm" | "md";
}) {
  return (
    <div className={`segmented segmented--${size}`} role="radiogroup" aria-label={ariaLabel}>
      {options.map((option) => {
        const checked = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={checked}
            className={checked ? "segmented__item segmented__item--active" : "segmented__item"}
            onClick={() => onChange(option.value)}
          >
            {option.icon}
            {option.label != null && <span>{option.label}</span>}
          </button>
        );
      })}
    </div>
  );
}
