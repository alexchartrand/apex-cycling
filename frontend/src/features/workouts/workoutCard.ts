import type { Formatters } from "../../i18n/format";
import { formatRecordTime } from "../records/timeInput";
import { EVENT_DISTANCE_M, EVENT_START_TYPES, type StandardEventKey } from "../records/types";
import { CARD_PALETTE } from "../share/shareCard";
import { clockText, lengthText, profileBars, type BarTone } from "./profile";
import { gearKey, isRepeat, type InnerRepeat, type ProfileSegment, type StepKind, type WorkoutEstimate, type WorkoutItem, type WorkoutStep } from "./types";

/*
  The workout as a picture to ride with (W7): a phone lock screen (dark, the
  top left free for the clock) or a narrow strip to print and tape to the
  stem (light, so it prints). The steps stay as written — repeats are not
  unrolled, so "8 ×" stays one line — with power in watts when the FTP is
  known and a track step's time: its target, else the athlete's best.
*/

export type WorkoutCardSize = "phone" | "stem";
export const WORKOUT_CARD_SIZES: WorkoutCardSize[] = ["phone", "stem"];

interface CardLayout {
  width: number;
  height: number;
  /** Where the content starts and stops: a lock screen's clock and its bottom buttons are left free. */
  top: number;
  bottom: number;
  margin: number;
  palette: CardColors;
  /** Font size of a step line at scale 1; rows shrink from it to fit, or grow up to `maxScale` when there is room. */
  rowPx: number;
  maxScale: number;
  titlePx: number;
  profileHeight: number;
  indent: number;
}

interface CardColors {
  ground: string;
  text: string;
  textMuted: string;
  line: string;
  tones: Record<BarTone, string>;
}

/** The stem card is printed: dark ink on white, tones that stay apart in greyscale. */
const PRINT_COLORS: CardColors = {
  ground: "#FFFFFF",
  text: "#111111",
  textMuted: "#4A4A4A",
  line: "#9A9A9A",
  tones: { easy: "#8BA0D9", recovery: "#BDBDBD", work: "#2D46A8", track: "#C8323A" },
};

const NIGHT_COLORS: CardColors = {
  ground: CARD_PALETTE.ground,
  text: CARD_PALETTE.text,
  textMuted: CARD_PALETTE.textMuted,
  line: CARD_PALETTE.line,
  tones: { easy: "#5B6C9E", recovery: "#3B4763", work: CARD_PALETTE.accent, track: CARD_PALETTE.marker },
};

export const CARD_LAYOUTS: Record<WorkoutCardSize, CardLayout> = {
  // 9:16 at phone resolution; iOS and Android draw the clock over the top ~25 %.
  phone: { width: 1080, height: 1920, top: 560, bottom: 1740, margin: 72, palette: NIGHT_COLORS, rowPx: 46, maxScale: 1.15, titlePx: 72, profileHeight: 110, indent: 40 },
  // 5 × 15 cm at 300 dpi.
  stem: { width: 600, height: 1800, top: 48, bottom: 1752, margin: 36, palette: PRINT_COLORS, rowPx: 34, maxScale: 1.6, titlePx: 48, profileHeight: 80, indent: 26 },
};

export interface WorkoutCardRow {
  depth: number;
  /** A repeat's own line ("8 ×") has no kind. */
  kind: StepKind | null;
  isTrack: boolean;
  /** "5:00", "3 laps", "500 m"; null for a repeat line. */
  length: string | null;
  label: string;
  /** "250–270 W · 95 rpm · 11.200 s · 50×15", notes last. */
  detail: string | null;
}

export interface WorkoutCardModel {
  brand: string;
  title: string;
  /** "Tue, Nov 11 · 1 h 05 · 62 TSS" */
  subtitle: string;
  segments: ProfileSegment[];
  rows: WorkoutCardRow[];
  /** "Watts at FTP 280 W", or why they are in % FTP. */
  footer: string | null;
}

/** Words the caller translates; the builder only adds numbers. */
export interface WorkoutCardTexts {
  brand: string;
  kind: (kind: StepKind) => string;
  repeat: (count: number) => string;
  laps: (count: number) => string;
  open: string;
  event: (eventKey: StandardEventKey) => string;
  start: (startType: "standing" | "flying") => string;
  rpe: (value: number) => string;
  /** "best 11.420 s": a track step's time when it has no target. */
  best: (time: string) => string;
  tss: (value: string) => string;
  ftp: (watts: string) => string;
  noFtp: string;
  units: { ftpPct: string; w: string; rpm: string };
}

export interface WorkoutCardInput {
  name: string;
  /** The planned day, already formatted; null for a library workout. */
  date: string | null;
  steps: WorkoutItem[];
  estimate: WorkoutEstimate | null;
  ftpW: number | null;
  /** Best time per `bestKey(event, start)`, from the records board. */
  bests: Record<string, number>;
  /** `gearKey` → the athlete's own name for that gear. */
  gearLabels?: Record<string, string>;
}

export type WorkoutCardFormat = Pick<Formatters, "number" | "distance" | "seconds" | "lapTime">;

export const bestKey = (eventKey: string, startType: string | null) => `${eventKey}|${startType ?? "flying"}`;

/** The best time per event and start of a records board (any track). */
export function bestTimes(records: { event_key: string; start_type: string; time_ms: number }[]): Record<string, number> {
  const bests: Record<string, number> = {};
  for (const record of records) {
    const key = bestKey(record.event_key, record.start_type);
    if (bests[key] == null || record.time_ms < bests[key]) bests[key] = record.time_ms;
  }
  return bests;
}

/** A power target as the rider reads it: watts when the FTP is known, else as written. */
export function powerText(step: WorkoutStep, ftpW: number | null, texts: Pick<WorkoutCardTexts, "units">, fmt: Pick<Formatters, "number">): string | null {
  const power = step.power;
  if (!power) return null;
  const values = power.high != null && power.high !== power.low ? [power.low, power.high] : [power.low];
  if (power.unit === "watts") return `${values.map((v) => fmt.number(v, 0)).join("–")} ${texts.units.w}`;
  if (ftpW != null) return `${values.map((v) => fmt.number(Math.round((v / 100) * ftpW), 0)).join("–")} ${texts.units.w}`;
  return `${values.map((v) => fmt.number(v, 0)).join("–")} ${texts.units.ftpPct}`;
}

function stepLength(step: WorkoutStep, texts: WorkoutCardTexts, fmt: WorkoutCardFormat): string {
  if (step.duration_s != null) return clockText(step.duration_s);
  if (step.distance_m != null) return fmt.distance(step.distance_m);
  if (step.laps != null) return texts.laps(step.laps);
  if (step.event_key) {
    const distance = EVENT_DISTANCE_M[step.event_key];
    return distance != null ? fmt.distance(distance) : texts.laps(1);
  }
  return texts.open;
}

function stepRow(step: WorkoutStep, depth: number, input: WorkoutCardInput, texts: WorkoutCardTexts, fmt: WorkoutCardFormat): WorkoutCardRow {
  // A flying 200 or a lap has only the one start: saying it again is noise.
  const start = step.event_key && step.start_type && EVENT_START_TYPES[step.event_key].length > 1 ? texts.start(step.start_type) : null;
  const event = step.event_key ? [texts.event(step.event_key), start].filter(Boolean).join(" · ") : null;
  const best = step.event_key && step.target_time_ms == null ? input.bests[bestKey(step.event_key, step.start_type)] : undefined;
  // The saved gear's "Bike · 50×15" with a space, so the detail never wraps inside it.
  const gear = step.gear
    ? (input.gearLabels?.[gearKey(step.gear.chainring_teeth, step.gear.cog_teeth)]?.replaceAll(" · ", " ") ?? gearKey(step.gear.chainring_teeth, step.gear.cog_teeth))
    : null;
  const cadence = step.cadence
    ? `${step.cadence.high != null && step.cadence.high !== step.cadence.low ? `${step.cadence.low}–${step.cadence.high}` : step.cadence.low} ${texts.units.rpm}`
    : null;
  const detail = [
    step.label && event ? event : null,
    powerText(step, input.ftpW, texts, fmt),
    cadence,
    step.target_time_ms != null ? formatRecordTime(step.target_time_ms, fmt) : best != null ? texts.best(formatRecordTime(best, fmt)) : null,
    gear,
    step.rpe != null ? texts.rpe(step.rpe) : null,
    step.notes?.trim() || null,
  ].filter(Boolean);
  return {
    depth,
    kind: step.kind,
    isTrack: step.event_key != null,
    length: stepLength(step, texts, fmt),
    label: step.label ?? event ?? texts.kind(step.kind),
    detail: detail.length > 0 ? detail.join(" · ") : null,
  };
}

export function cardRows(items: (WorkoutItem | InnerRepeat)[], input: WorkoutCardInput, texts: WorkoutCardTexts, fmt: WorkoutCardFormat, depth = 0): WorkoutCardRow[] {
  return items.flatMap((item) =>
    isRepeat(item)
      ? [
          { depth, kind: null, isTrack: false, length: null, label: texts.repeat(item.count), detail: null },
          ...cardRows(item.steps, input, texts, fmt, depth + 1),
        ]
      : [stepRow(item, depth, input, texts, fmt)],
  );
}

function hasPercentTargets(items: (WorkoutItem | InnerRepeat)[]): boolean {
  return items.some((item) => (isRepeat(item) ? hasPercentTargets(item.steps) : item.power?.unit === "ftp_pct"));
}

export function workoutCardModel(input: WorkoutCardInput, texts: WorkoutCardTexts, fmt: WorkoutCardFormat): WorkoutCardModel {
  const estimate = input.estimate;
  const subtitle = [
    input.date,
    estimate && estimate.duration_s > 0 ? lengthText(estimate.duration_s) : null,
    estimate?.tss != null ? texts.tss(fmt.number(estimate.tss, 0)) : null,
  ].filter(Boolean);
  const percent = hasPercentTargets(input.steps);
  return {
    brand: texts.brand,
    title: input.name,
    subtitle: subtitle.join(" · "),
    segments: estimate?.segments ?? [],
    rows: cardRows(input.steps, input, texts, fmt),
    footer: !percent ? null : input.ftpW != null ? texts.ftp(fmt.number(input.ftpW, 0)) : texts.noFtp,
  };
}

/** How tall a row is, in multiples of the row font size: the step line, then its detail lines. */
export function rowUnits(detailLines: number): number {
  return 1.45 + detailLines * 1.05;
}

/**
 * The biggest scale (≤ `maxScale`) at which the rows fit, `detailLines` giving
 * a row's wrapped detail at a scale; under `minScale`, the same without
 * details; still too tall, as many rows as fit at `minScale` with a line kept
 * for "+ N more".
 */
export function fitRows(
  rows: WorkoutCardRow[],
  available: number,
  rowPx: number,
  detailLines: (row: WorkoutCardRow, scale: number) => number = (row) => (row.detail ? 1 : 0),
  maxScale = 1,
  minScale = 0.55,
  /** Whether the step lines fit across at a scale (only scales ≤ 1 are tried when they don't). */
  fitsAcross: (scale: number) => boolean = () => true,
): { scale: number; withDetail: boolean; shown: number } {
  const height = (scale: number, withDetail: boolean) =>
    rows.reduce((sum, row) => sum + rowPx * scale * rowUnits(withDetail ? detailLines(row, scale) : 0), 0);
  for (const withDetail of [true, false]) {
    for (let step = 0; maxScale - step * 0.05 >= minScale - 1e-9; step += 1) {
      const scale = Math.round((maxScale - step * 0.05) * 100) / 100;
      if (scale > 1 && !fitsAcross(scale)) continue;
      if (height(scale, withDetail) <= available) return { scale, withDetail, shown: rows.length };
    }
  }
  let used = rowPx * minScale * rowUnits(0);
  let shown = 0;
  while (shown < rows.length && used + rowPx * minScale * rowUnits(0) <= available) {
    used += rowPx * minScale * rowUnits(0);
    shown += 1;
  }
  return { scale: minScale, withDetail: false, shown };
}

export function workoutCardFileName(title: string, size: WorkoutCardSize): string {
  const slug = title
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return `apex-${slug || "workout"}-${size}.png`;
}

type Ctx = CanvasRenderingContext2D;

const DISPLAY_FONT = `"Barlow Condensed", "Arial Narrow", system-ui, sans-serif`;
const BODY_FONT = `"Inter Variable", "Inter", system-ui, "Segoe UI", Roboto, sans-serif`;

/** `text` cut with an ellipsis to `maxWidth` at the current font. */
export function clipText(ctx: Pick<Ctx, "measureText">, text: string, maxWidth: number): string {
  if (ctx.measureText(text).width <= maxWidth) return text;
  let end = text.length;
  while (end > 1 && ctx.measureText(`${text.slice(0, end).trimEnd()}…`).width > maxWidth) end -= 1;
  return `${text.slice(0, end).trimEnd()}…`;
}

/**
 * `text` over at most `maxLines` lines of `maxWidth`, broken between its
 * " · " parts (between words only inside a part too long for a line), the
 * last line cut with an ellipsis.
 */
export function wrapText(ctx: Pick<Ctx, "measureText">, text: string, maxWidth: number, maxLines: number): string[] {
  const fits = (candidate: string) => ctx.measureText(candidate).width <= maxWidth;
  // Each piece with what joins it to the previous one on the same line.
  const pieces = text
    .split(" · ")
    .flatMap((part) => {
      const trimmed = part.trim();
      if (!trimmed) return [];
      if (fits(trimmed)) return [{ glue: " · ", text: trimmed }];
      return trimmed.split(/\s+/).map((word, index) => ({ glue: index === 0 ? " · " : " ", text: word }));
    });
  const lines: string[] = [];
  let line = "";
  for (let index = 0; index < pieces.length; index += 1) {
    const piece = pieces[index];
    const candidate = line ? `${line}${piece.glue}${piece.text}` : piece.text;
    if (fits(candidate) || !line) {
      line = candidate;
      continue;
    }
    if (lines.length === maxLines - 1) {
      const rest = pieces.slice(index).map((p) => `${p.glue}${p.text}`).join("");
      return [...lines, clipText(ctx, `${line}${rest}`, maxWidth)];
    }
    lines.push(clipText(ctx, line, maxWidth));
    line = piece.text;
  }
  if (line) lines.push(clipText(ctx, line, maxWidth));
  return lines;
}

const MAX_DETAIL_LINES = 3;

function fitFont(ctx: Ctx, text: string, font: (px: number) => string, startPx: number, maxWidth: number, minPx: number) {
  let px = startPx;
  ctx.font = font(px);
  while (px > minPx && ctx.measureText(text).width > maxWidth) {
    px -= 2;
    ctx.font = font(px);
  }
}

function drawProfile(ctx: Ctx, segments: ProfileSegment[], colors: CardColors, box: { x: number; y: number; width: number; height: number }) {
  const bars = profileBars(segments);
  if (bars.length === 0) return;
  ctx.fillStyle = colors.line;
  ctx.fillRect(box.x, box.y + box.height, box.width, 2);
  for (const bar of bars) {
    const height = Math.max(3, bar.height * box.height);
    ctx.globalAlpha = bar.unrated ? 0.45 : 1;
    ctx.fillStyle = colors.tones[bar.tone];
    // A hairline between steps so short repeats stay countable.
    const width = Math.max(1, bar.width * box.width - 1);
    ctx.fillRect(box.x + bar.x * box.width, box.y + box.height - height, width, height);
  }
  ctx.globalAlpha = 1;
}

function rowTone(row: WorkoutCardRow): BarTone | null {
  if (row.kind == null) return null;
  if (row.kind === "warmup" || row.kind === "cooldown") return "easy";
  if (row.kind === "recovery") return "recovery";
  return row.isTrack ? "track" : "work";
}

/** Draws the card onto a canvas of `CARD_LAYOUTS[size]`'s width and height. */
export function drawWorkoutCard(ctx: Ctx, model: WorkoutCardModel, size: WorkoutCardSize, moreText: (count: number) => string): void {
  const layout = CARD_LAYOUTS[size];
  const { width, margin, palette: colors } = layout;
  const inner = width - margin * 2;

  ctx.fillStyle = colors.ground;
  ctx.fillRect(0, 0, width, layout.height);
  ctx.textBaseline = "alphabetic";
  ctx.textAlign = "left";

  let y = layout.top;
  ctx.fillStyle = colors.textMuted;
  ctx.font = `700 ${Math.round(layout.rowPx * 0.62)}px ${DISPLAY_FONT}`;
  y += layout.rowPx * 0.62;
  ctx.fillText(model.brand.toUpperCase(), margin, y);

  ctx.fillStyle = colors.text;
  fitFont(ctx, model.title, (px) => `700 ${px}px ${DISPLAY_FONT}`, layout.titlePx, inner, Math.round(layout.titlePx * 0.6));
  y += layout.titlePx * 1.05;
  ctx.fillText(clipText(ctx, model.title, inner), margin, y);

  if (model.subtitle) {
    ctx.fillStyle = colors.textMuted;
    ctx.font = `500 ${Math.round(layout.rowPx * 0.7)}px ${BODY_FONT}`;
    y += layout.rowPx * 1.05;
    ctx.fillText(clipText(ctx, model.subtitle, inner), margin, y);
  }

  if (model.segments.length > 0) {
    y += layout.rowPx * 0.6;
    drawProfile(ctx, model.segments, colors, { x: margin, y, width: inner, height: layout.profileHeight });
    y += layout.profileHeight + layout.rowPx * 0.4;
  }

  const footerHeight = model.footer ? layout.rowPx * 1.2 : 0;
  const available = layout.bottom - footerHeight - y;
  const fonts = (scale: number) => {
    const px = layout.rowPx * scale;
    return {
      length: `700 ${Math.round(px * 1.05)}px ${DISPLAY_FONT}`,
      label: `600 ${Math.round(px * 0.8)}px ${BODY_FONT}`,
      detail: `500 ${Math.round(px * 0.68)}px ${BODY_FONT}`,
    };
  };
  const marker = (scale: number) => Math.max(6, Math.round(layout.rowPx * scale * 0.22));
  // The detail sits under the length, from the step's own indent to the right edge.
  const detailX = (row: WorkoutCardRow, scale: number) => margin + row.depth * layout.indent + marker(scale) + layout.rowPx * scale * 0.35;
  // One column for the lengths, as wide as the widest of them.
  const lengthColumn = (scale: number) => {
    ctx.font = fonts(scale).length;
    return Math.max(0, ...model.rows.map((row) => (row.length ? ctx.measureText(row.length).width : 0)));
  };
  const labelX = (row: WorkoutCardRow, scale: number) => detailX(row, scale) + lengthColumn(scale) + layout.rowPx * scale * 0.5;
  // A label that doesn't fit beside its length opens the detail lines instead.
  const parts = (row: WorkoutCardRow, scale: number): { label: string; detail: string | null } => {
    if (row.kind == null) return { label: row.label, detail: null };
    ctx.font = fonts(scale).label;
    if (ctx.measureText(row.label).width <= margin + inner - labelX(row, scale)) return { label: row.label, detail: row.detail };
    return { label: "", detail: row.detail ? `${row.label} · ${row.detail}` : row.label };
  };
  const detailLines = (row: WorkoutCardRow, scale: number) => {
    const { detail } = parts(row, scale);
    if (!detail) return 0;
    ctx.font = fonts(scale).detail;
    return wrapText(ctx, detail, margin + inner - detailX(row, scale), MAX_DETAIL_LINES).length;
  };
  const maxDepth = Math.max(0, ...model.rows.map((row) => row.depth));
  const fitsAcross = (scale: number) => lengthColumn(scale) <= (inner - maxDepth * layout.indent) * 0.45;
  const fit = fitRows(model.rows, available, layout.rowPx, detailLines, layout.maxScale, 0.55, fitsAcross);
  const rowPx = layout.rowPx * fit.scale;
  const { length: lengthFont, label: labelFont, detail: detailFont } = fonts(fit.scale);
  const shown = model.rows.slice(0, fit.shown);
  const lengthWidth = lengthColumn(fit.scale);
  const markerWidth = marker(fit.scale);

  for (const row of shown) {
    const x = margin + row.depth * layout.indent;
    const lineTop = y;
    const { label, detail } = fit.withDetail ? parts(row, fit.scale) : { label: row.label, detail: null };
    y += rowPx * 1.1;
    if (row.kind == null) {
      ctx.fillStyle = colors.text;
      ctx.font = lengthFont;
      ctx.fillText(row.label, x, y);
    } else {
      const tone = rowTone(row);
      if (tone) {
        ctx.fillStyle = colors.tones[tone];
        ctx.fillRect(x, y - rowPx * 0.8, markerWidth, rowPx * 0.8);
      }
      const textX = detailX(row, fit.scale);
      ctx.fillStyle = colors.text;
      ctx.font = lengthFont;
      const lengthText = row.length ? clipText(ctx, row.length, lengthWidth) : "";
      ctx.fillText(lengthText, textX, y);
      const labelLeft = textX + lengthWidth + rowPx * 0.5;
      ctx.font = labelFont;
      if (label) ctx.fillText(clipText(ctx, label, margin + inner - labelLeft), labelLeft, y);
      if (detail) {
        ctx.fillStyle = colors.textMuted;
        ctx.font = detailFont;
        for (const line of wrapText(ctx, detail, margin + inner - textX, MAX_DETAIL_LINES)) {
          y += rowPx * 1.05;
          ctx.fillText(line, textX, y);
        }
      }
    }
    y = lineTop + rowPx * rowUnits(detail ? detailLines(row, fit.scale) : 0);
    // Steps inside a repeat hang off a rule, so where the block ends shows.
    if (row.depth > 0) {
      ctx.fillStyle = colors.line;
      for (let depth = 1; depth <= row.depth; depth += 1) ctx.fillRect(margin + (depth - 1) * layout.indent + 6, lineTop, 3, y - lineTop);
    }
  }

  if (fit.shown < model.rows.length) {
    ctx.fillStyle = colors.textMuted;
    ctx.font = labelFont;
    y += rowPx * 1.1;
    ctx.fillText(moreText(model.rows.length - fit.shown), margin, y);
  }

  if (model.footer) {
    ctx.fillStyle = colors.textMuted;
    ctx.font = `500 ${Math.round(layout.rowPx * 0.6)}px ${BODY_FONT}`;
    // Right under the steps, so a short strip can be cut short.
    ctx.fillText(clipText(ctx, model.footer, inner), margin, Math.min(layout.bottom, y + layout.rowPx * 1.1));
  }
}
