import type { ReactElement, ReactNode } from "react";
import { ResponsiveContainer } from "recharts";
import "./charts.css";

export type LegendItem = { label: ReactNode; color: string; dashed?: boolean };

/**
 * Fixed-height responsive box for one Recharts chart, with an optional
 * legend and an empty state (Recharts renders a blank canvas otherwise).
 * `children` is the chart element itself (LineChart, AreaChart…).
 */
export function ChartFrame({
  height = 240,
  legend,
  isEmpty = false,
  emptyMessage = "No data to chart yet.",
  caption,
  children,
}: {
  height?: number;
  legend?: LegendItem[];
  isEmpty?: boolean;
  emptyMessage?: ReactNode;
  caption?: ReactNode;
  children: ReactNode;
}) {
  return (
    <figure className="chart-frame">
      {isEmpty ? (
        <div className="chart-frame__empty" style={{ height }}>
          {emptyMessage}
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={height}>
          {children as ReactElement}
        </ResponsiveContainer>
      )}
      {(legend || caption) && (
        <figcaption className="chart-frame__foot">
          {legend && (
            <span className="chart-legend">
              {legend.map((item, i) => (
                <span key={i} className="chart-legend__item">
                  <span
                    className={item.dashed ? "chart-legend__swatch chart-legend__swatch--dashed" : "chart-legend__swatch"}
                    style={{ ["--swatch" as string]: item.color }}
                  />
                  {item.label}
                </span>
              ))}
            </span>
          )}
          {caption && <span className="chart-frame__caption">{caption}</span>}
        </figcaption>
      )}
    </figure>
  );
}
