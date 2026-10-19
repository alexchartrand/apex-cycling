/*
  Shared Recharts styling so every chart reads as one system. Colors are
  CSS variables from theme/tokens.css, which work in SVG presentation
  attributes (stroke/fill) and so follow the active theme with no re-render.
  Gradient <stop> colors are the exception — var() doesn't resolve there —
  so area fills use a flat fill + fillOpacity instead of gradients.
*/

export const CHART_SERIES = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--chart-6)",
] as const;

export function seriesColor(index: number): string {
  return CHART_SERIES[index % CHART_SERIES.length];
}

export const axisProps = {
  tickLine: false,
  axisLine: false,
  tick: { fill: "var(--chart-axis)", fontSize: 12 },
} as const;

export const gridProps = {
  vertical: false,
  stroke: "var(--chart-grid)",
} as const;

export const cursorProps = { stroke: "var(--color-border-strong)", strokeWidth: 1 } as const;
