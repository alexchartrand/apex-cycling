import type { ReactNode } from "react";
import "./charts.css";

type Entry = {
  name?: string | number;
  value?: number | string | readonly (number | string)[];
  color?: string;
  dataKey?: string | number | ((obj: unknown) => unknown);
};

/**
 * Drop-in `content` for Recharts' <Tooltip>:
 *   <Tooltip content={<ChartTooltip formatValue={formatMs} />} />
 * Recharts injects active/payload/label.
 */
export function ChartTooltip({
  active,
  payload,
  label,
  formatValue = (v) => String(v),
  formatLabel = (l) => l,
}: {
  active?: boolean;
  payload?: readonly Entry[];
  label?: ReactNode;
  formatValue?: (value: number, name: string) => ReactNode;
  formatLabel?: (label: ReactNode) => ReactNode;
}) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="chart-tooltip">
      {label != null && <div className="chart-tooltip__label">{formatLabel(label)}</div>}
      {payload
        .filter((entry) => entry.value != null)
        .map((entry) => (
          <div key={String(entry.dataKey ?? entry.name)} className="chart-tooltip__row">
            <span className="chart-tooltip__dot" style={{ background: entry.color }} />
            <span className="chart-tooltip__name">{entry.name}</span>
            <span className="chart-tooltip__value">{formatValue(Number(entry.value), String(entry.name))}</span>
          </div>
        ))}
    </div>
  );
}
