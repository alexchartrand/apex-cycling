import type { Formatters } from "../../i18n/format";
import { EVENT_DISTANCE_M, type StandardEventKey } from "../records/types";
import { bounds, buildVelodrome, offsetPoint, type Velodrome } from "../training/velodromeGeometry";
import type { LapDetail } from "../training/types";

export const CARD_WIDTH = 1080;
export const CARD_HEIGHT = 1350;

/**
 * The card is always the dark "night session" look, whatever theme the app is
 * in — it is an image people post, so it can't follow the viewer's setting.
 * That is why these are fixed values rather than tokens.
 */
export const CARD_PALETTE = {
  ground: "#0B1220",
  panel: "#121B2E",
  line: "#33415F",
  text: "#EEE8D7",
  textMuted: "#A6AFC4",
  accent: "#8FA3F2",
  marker: "#FF7378",
  highlight: "#E9B35E",
} as const;

export interface CardSplit {
  label: string;
  ms: number;
}

/** Everything the card shows, already formatted for the viewer's language. */
export interface ShareCardModel {
  brand: string;
  /** "Record · Standing start" */
  eyebrow: string;
  /** "500 m" */
  title: string;
  /** "47.535 s" / "1:12.345" */
  time: string;
  /** "−3.899 s" with what it is against, when known. */
  delta: string | null;
  deltaNote: string | null;
  place: string;
  date: string;
  splitsCaption: string;
  splits: CardSplit[];
  trackLengthM: number | null;
}

export type CardFormat = Pick<Formatters, "seconds" | "lapTime" | "deltaSeconds" | "date">;

export function recordTimeText(ms: number, fmt: Pick<Formatters, "seconds" | "lapTime">): string {
  return ms < 60_000 ? `${fmt.seconds(ms)} s` : fmt.lapTime(ms);
}

/**
 * The laps a standard-distance performance was ridden in: `lapCount` laps from
 * `firstLapId` in time order. Empty when the first lap isn't in the list or the
 * run is cut short or has a lap without a time.
 */
export function windowSplits(laps: LapDetail[], firstLapId: string | null, lapCount: number): CardSplit[] {
  if (!firstLapId || lapCount < 1) return [];
  const ordered = [...laps].sort((a, b) => a.start_time.localeCompare(b.start_time));
  const first = ordered.findIndex((lap) => lap.lap_id === firstLapId);
  if (first < 0) return [];
  const window = ordered.slice(first, first + lapCount);
  if (window.length < lapCount || window.some((lap) => lap.whole_lap_time_ms == null)) return [];
  return window.map((lap, index) => ({ label: String(index + 1), ms: lap.whole_lap_time_ms! }));
}

/** How many laps of this track make a standard event (1 for "lap", none for the view-timed 200). */
export function eventLapCount(eventKey: string, trackLengthM: number | null): number {
  if (eventKey === "lap") return 1;
  const distance = EVENT_DISTANCE_M[eventKey as StandardEventKey];
  if (!distance || eventKey === "f200" || !trackLengthM) return 0;
  const count = Math.round(distance / trackLengthM);
  return count >= 1 && Math.abs(count * trackLengthM - distance) <= 0.5 ? count : 0;
}

/** Bars for the splits: heights scale between a floor under the fastest lap and the slowest. */
export function splitBarHeights(splits: CardSplit[], maxHeight: number, minHeight = 0.35 * maxHeight): number[] {
  if (splits.length === 0) return [];
  const fastest = Math.min(...splits.map((s) => s.ms));
  const slowest = Math.max(...splits.map((s) => s.ms));
  if (slowest === fastest) return splits.map(() => maxHeight);
  // The slowest lap is the tallest bar: height = time, so a slower lap reads as more.
  return splits.map((s) => minHeight + ((s.ms - fastest) / (slowest - fastest)) * (maxHeight - minHeight));
}

export function shareFileName(model: Pick<ShareCardModel, "title" | "date">): string {
  const slug = `${model.title}-${model.date}`
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return `apex-${slug || "card"}.png`;
}

type Ctx = CanvasRenderingContext2D;

const DISPLAY_FONT = `"Barlow Condensed", "Arial Narrow", system-ui, sans-serif`;
const BODY_FONT = `"Inter Variable", "Inter", system-ui, "Segoe UI", Roboto, sans-serif`;

function fitText(ctx: Ctx, text: string, font: (px: number) => string, startPx: number, maxWidth: number): number {
  let px = startPx;
  ctx.font = font(px);
  while (px > 24 && ctx.measureText(text).width > maxWidth) {
    px -= 4;
    ctx.font = font(px);
  }
  return px;
}

function drawTrack(ctx: Ctx, track: Velodrome, box: { x: number; y: number; width: number; height: number }) {
  const outer = bounds(track, 6.8);
  const scale = Math.min(box.width / outer.width, box.height / outer.height);
  const originX = box.x + (box.width - outer.width * scale) / 2 - outer.minX * scale;
  const originY = box.y + (box.height - outer.height * scale) / 2 - outer.minY * scale;
  const trace = (offset: number) => {
    ctx.beginPath();
    track.samples.forEach((sample, index) => {
      const p = offsetPoint(sample, offset);
      const x = originX + p.x * scale;
      const y = originY + p.y * scale;
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.closePath();
  };

  trace(6.8);
  ctx.fillStyle = CARD_PALETTE.panel;
  ctx.fill();
  ctx.lineWidth = 3;
  ctx.strokeStyle = CARD_PALETTE.line;
  ctx.stroke();
  trace(-0.2);
  ctx.fillStyle = CARD_PALETTE.ground;
  ctx.fill();
  ctx.stroke();
  trace(0.65); // the sprinter's line
  ctx.lineWidth = 3;
  ctx.strokeStyle = CARD_PALETTE.marker;
  ctx.stroke();

  // Start/finish: where the home straight's midpoint (s = 0) is.
  const start = offsetPoint(track.samples[0], 0.65);
  ctx.beginPath();
  ctx.arc(originX + start.x * scale, originY + start.y * scale, 11, 0, Math.PI * 2);
  ctx.fillStyle = CARD_PALETTE.text;
  ctx.fill();
}

/** Draws the card onto a CARD_WIDTH × CARD_HEIGHT canvas context. */
export function drawShareCard(ctx: Ctx, model: ShareCardModel): void {
  const margin = 72;
  const inner = CARD_WIDTH - margin * 2;

  ctx.fillStyle = CARD_PALETTE.ground;
  ctx.fillRect(0, 0, CARD_WIDTH, CARD_HEIGHT);
  ctx.fillStyle = CARD_PALETTE.marker;
  ctx.fillRect(0, 0, 14, CARD_HEIGHT);

  ctx.textBaseline = "alphabetic";
  ctx.textAlign = "left";
  ctx.fillStyle = CARD_PALETTE.text;
  ctx.font = `700 44px ${DISPLAY_FONT}`;
  ctx.fillText(model.brand.toUpperCase(), margin, 110);
  ctx.textAlign = "right";
  ctx.fillStyle = CARD_PALETTE.textMuted;
  ctx.font = `500 32px ${BODY_FONT}`;
  ctx.fillText(model.date, CARD_WIDTH - margin, 108);

  if (model.trackLengthM) {
    drawTrack(ctx, buildVelodrome(model.trackLengthM, 600), { x: margin, y: 150, width: inner, height: 330 });
  }

  ctx.textAlign = "left";
  ctx.fillStyle = CARD_PALETTE.highlight;
  ctx.font = `600 36px ${BODY_FONT}`;
  ctx.fillText(model.eyebrow.toUpperCase(), margin, 570);

  ctx.fillStyle = CARD_PALETTE.text;
  ctx.font = `700 120px ${DISPLAY_FONT}`;
  ctx.fillText(model.title, margin, 690);

  const timeFont = (px: number) => `700 ${px}px ${DISPLAY_FONT}`;
  fitText(ctx, model.time, timeFont, 280, inner);
  ctx.fillStyle = CARD_PALETTE.text;
  ctx.fillText(model.time, margin, 930);

  if (model.delta) {
    ctx.font = `700 56px ${DISPLAY_FONT}`;
    ctx.fillStyle = CARD_PALETTE.accent;
    ctx.fillText(model.delta, margin, 1010);
    if (model.deltaNote) {
      const width = ctx.measureText(model.delta).width;
      ctx.font = `500 32px ${BODY_FONT}`;
      ctx.fillStyle = CARD_PALETTE.textMuted;
      ctx.fillText(model.deltaNote, margin + width + 24, 1008);
    }
  } else if (model.deltaNote) {
    ctx.font = `500 32px ${BODY_FONT}`;
    ctx.fillStyle = CARD_PALETTE.textMuted;
    ctx.fillText(model.deltaNote, margin, 1008);
  }

  if (model.splits.length > 0) {
    ctx.font = `600 28px ${BODY_FONT}`;
    ctx.fillStyle = CARD_PALETTE.textMuted;
    ctx.fillText(model.splitsCaption.toUpperCase(), margin, 1090);

    const base = 1245;
    const maxHeight = 96;
    const heights = splitBarHeights(model.splits, maxHeight);
    const gap = model.splits.length > 12 ? 8 : 14;
    const barWidth = Math.min(80, (inner - gap * (model.splits.length - 1)) / model.splits.length);
    ctx.fillStyle = CARD_PALETTE.accent;
    ctx.textAlign = "center";
    model.splits.forEach((split, index) => {
      const x = margin + index * (barWidth + gap);
      ctx.fillStyle = CARD_PALETTE.accent;
      ctx.fillRect(x, base - heights[index], barWidth, heights[index]);
      if (barWidth >= 44) {
        ctx.fillStyle = CARD_PALETTE.text;
        ctx.font = `600 ${barWidth >= 60 ? 24 : 20}px ${BODY_FONT}`;
        ctx.fillText((split.ms / 1000).toFixed(1), x + barWidth / 2, base - heights[index] - 10);
      }
    });
    ctx.textAlign = "left";
  }

  ctx.fillStyle = CARD_PALETTE.textMuted;
  ctx.font = `500 30px ${BODY_FONT}`;
  ctx.fillText(model.place, margin, CARD_HEIGHT - 52);
}
