import type { ReactNode } from "react";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import "./StatTile.css";

export type DeltaDirection = "better" | "worse" | "neutral";

type StatTileProps = {
  label: ReactNode;
  value: ReactNode;
  unit?: ReactNode;
  delta?: { label: ReactNode; direction: DeltaDirection };
  hint?: ReactNode;
  icon?: ReactNode;
  tone?: "default" | "accent" | "marker" | "highlight";
  size?: "md" | "lg";
  className?: string;
};

const DELTA_ICONS = { better: ArrowUpRight, worse: ArrowDownRight, neutral: Minus };

/**
 * One headline number in the timing-board display face. `delta.direction`
 * is semantic (better/worse), not numeric, since for lap times a *lower*
 * number is the improvement.
 */
export function StatTile({ label, value, unit, delta, hint, icon, tone = "default", size = "md", className }: StatTileProps) {
  const DeltaIcon = delta ? DELTA_ICONS[delta.direction] : null;
  return (
    <div className={["stat-tile", `stat-tile--${tone}`, `stat-tile--${size}`, className].filter(Boolean).join(" ")}>
      <div className="stat-tile__label">
        {icon}
        <span>{label}</span>
      </div>
      <div className="stat-tile__value">
        <span className="stat-tile__number">{value}</span>
        {unit != null && <span className="stat-tile__unit">{unit}</span>}
      </div>
      {(delta || hint) && (
        <div className="stat-tile__foot">
          {delta && DeltaIcon && (
            <span className={`stat-tile__delta stat-tile__delta--${delta.direction}`}>
              <DeltaIcon aria-hidden />
              {delta.label}
            </span>
          )}
          {hint != null && <span className="stat-tile__hint">{hint}</span>}
        </div>
      )}
    </div>
  );
}
