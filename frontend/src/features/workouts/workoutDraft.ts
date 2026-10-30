import type { Formatters } from "../../i18n/format";
import { parseTimeInput, timeToInput } from "../records/timeInput";
import { EVENT_START_TYPES, STANDARD_EVENT_KEYS, type StandardEventKey } from "../records/types";
import { isRepeat, type InnerRepeat, type StepKind, type Workout, type WorkoutItem, type WorkoutStep, type WorkoutWrite } from "./types";

/*
  The editor's copy of a workout: the step tree with every field as typed
  (like `planForm.ts`), and an id per node so React keys and the tree
  operations survive reordering. `draftPayload` turns it back into what the
  API takes, or null while something would be refused.
*/

// Bounds mirror backend `workouts/schemas.py`.
export const LIMITS = {
  durationS: 6 * 3600,
  distanceM: 100_000,
  laps: 400,
  ftpPct: 300,
  watts: 3000,
  cadence: { min: 20, max: 250 },
  count: { min: 2, max: 50 },
  chainring: { min: 10, max: 100 },
  cog: { min: 5, max: 60 },
  stepsPerRepeat: 20,
  topLevelItems: 50,
  structureSize: 100,
  tags: 10,
  tagLength: 30,
} as const;

export type LengthMode = "time" | "distance" | "laps" | "open";

export type DraftStep = {
  id: string;
  type: "step";
  kind: StepKind;
  label: string;
  notes: string;
  lengthMode: LengthMode;
  duration: string;
  distance: string;
  laps: string;
  /** "" = no power target. */
  powerUnit: "" | "ftp_pct" | "watts";
  powerLow: string;
  powerHigh: string;
  cadenceLow: string;
  cadenceHigh: string;
  /** "" = none, else "1"…"10". */
  rpe: string;
  eventKey: "" | StandardEventKey;
  startType: "" | "standing" | "flying";
  targetTime: string;
  chainring: string;
  cog: string;
};

export type DraftRepeat = { id: string; type: "repeat"; count: string; steps: DraftNode[] };
export type DraftNode = DraftStep | DraftRepeat;

export type WorkoutDraft = { name: string; description: string; tags: string; steps: DraftNode[] };

export type StepField =
  | "duration"
  | "distance"
  | "laps"
  | "powerLow"
  | "powerHigh"
  | "cadenceLow"
  | "cadenceHigh"
  | "targetTime"
  | "gear"
  | "count"
  | "empty";

export type DraftErrors = {
  name?: true;
  tags?: true;
  /** The whole tree: no step, or more than a head unit takes. */
  steps?: "empty" | "tooMany";
  nodes: Record<string, StepField[]>;
};

let sequence = 0;
const nextId = () => `n${++sequence}`;

// ---------------------------------------------------------------- text ⇄ values

/** "45" → 45 s, "1:30" → 90 s, "1:00:00" → 3600 s; null when it isn't one. */
export function parseDuration(text: string): number | null {
  const trimmed = text.trim();
  if (!/^\d{1,5}(?::\d{1,2}){0,2}$/.test(trimmed)) return null;
  const parts = trimmed.split(":").map(Number);
  if (parts.slice(1).some((part) => part >= 60)) return null;
  const seconds = parts.reduce((total, part) => total * 60 + part, 0);
  return seconds > 0 ? seconds : null;
}

/** 45 → "45", 90 → "1:30", 3600 → "1:00:00": what you'd type back in. */
export function durationToInput(seconds: number): string {
  const s = Math.round(seconds);
  if (s < 60) return String(s);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const rest = String(s % 60).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${rest}` : `${m}:${rest}`;
}

/** Blank → null, else the number (comma decimals too), NaN when it isn't one. */
function parseNumber(text: string): number | null {
  const trimmed = text.trim();
  if (trimmed === "") return null;
  return /^\d+([.,]\d+)?$/.test(trimmed) ? Number(trimmed.replace(",", ".")) : NaN;
}

const numberText = (value: number | null | undefined, decimal: string) => (value == null ? "" : String(value).replace(".", decimal));

const inRange = (value: number | null, min: number, max: number, integer = false) =>
  value != null && !Number.isNaN(value) && value >= min && value <= max && (!integer || Number.isInteger(value));

export function parseTags(text: string): string[] {
  const tags: string[] = [];
  for (const raw of text.split(",")) {
    const tag = raw.trim().toLowerCase();
    if (tag && !tags.includes(tag)) tags.push(tag);
  }
  return tags;
}

// ---------------------------------------------------------------- building

export function newStep(kind: StepKind = "work", duration = "5:00"): DraftStep {
  return {
    id: nextId(),
    type: "step",
    kind,
    label: "",
    notes: "",
    lengthMode: "time",
    duration,
    distance: "",
    laps: "",
    powerUnit: "",
    powerLow: "",
    powerHigh: "",
    cadenceLow: "",
    cadenceHigh: "",
    rpe: "",
    eventKey: "",
    startType: "",
    targetTime: "",
    chainring: "",
    cog: "",
  };
}

export function newRepeat(): DraftRepeat {
  return { id: nextId(), type: "repeat", count: "4", steps: [newStep("work", "1:00"), newStep("recovery", "1:00")] };
}

export function emptyDraft(): WorkoutDraft {
  return { name: "", description: "", tags: "", steps: [newStep("warmup", "10:00"), newStep("work", "20:00"), newStep("cooldown", "10:00")] };
}

type Fmt = Pick<Formatters, "seconds" | "lapTime" | "language">;

function stepDraft(step: WorkoutStep, fmt: Fmt): DraftStep {
  const decimal = fmt.language === "fr" ? "," : ".";
  const lengthMode: LengthMode = step.duration_s != null ? "time" : step.distance_m != null ? "distance" : step.laps != null ? "laps" : "open";
  return {
    ...newStep(step.kind ?? "work", ""),
    label: step.label ?? "",
    notes: step.notes ?? "",
    lengthMode,
    duration: step.duration_s != null ? durationToInput(step.duration_s) : "",
    distance: numberText(step.distance_m, decimal),
    laps: numberText(step.laps, decimal),
    powerUnit: step.power?.unit ?? "",
    powerLow: numberText(step.power?.low, decimal),
    powerHigh: numberText(step.power?.high, decimal),
    cadenceLow: numberText(step.cadence?.low, decimal),
    cadenceHigh: numberText(step.cadence?.high, decimal),
    rpe: step.rpe != null ? String(step.rpe) : "",
    eventKey: (STANDARD_EVENT_KEYS as readonly string[]).includes(step.event_key ?? "") ? (step.event_key as StandardEventKey) : "",
    startType: step.start_type ?? "",
    targetTime: step.target_time_ms != null ? timeToInput(step.target_time_ms, fmt) : "",
    chainring: numberText(step.gear?.chainring_teeth, decimal),
    cog: numberText(step.gear?.cog_teeth, decimal),
  };
}

function nodeDraft(item: WorkoutItem | InnerRepeat, fmt: Fmt): DraftNode {
  if (isRepeat(item)) return { id: nextId(), type: "repeat", count: String(item.count), steps: item.steps.map((child) => nodeDraft(child, fmt)) };
  return stepDraft(item, fmt);
}

export function draftFrom(workout: Pick<Workout, "name" | "description" | "tags" | "steps">, fmt: Fmt): WorkoutDraft {
  return {
    name: workout.name,
    description: workout.description ?? "",
    tags: workout.tags.join(", "),
    steps: workout.steps.map((item) => nodeDraft(item, fmt)),
  };
}

/** Changing the event keeps the start when the event has it, and clears the start and time when the event goes. */
export function withEvent(step: DraftStep, eventKey: "" | StandardEventKey): DraftStep {
  if (eventKey === "") return { ...step, eventKey, startType: "", targetTime: "" };
  const allowed = EVENT_START_TYPES[eventKey];
  return { ...step, eventKey, startType: step.startType && allowed.includes(step.startType) ? step.startType : "" };
}

// ---------------------------------------------------------------- tree operations

/** How deep `id` sits: 0 at the top level, 1 inside a repeat, 2 inside a repeat in a repeat; -1 when absent. */
export function depthOf(nodes: DraftNode[], id: string, depth = 0): number {
  for (const node of nodes) {
    if (node.id === id) return depth;
    if (node.type === "repeat") {
      const found = depthOf(node.steps, id, depth + 1);
      if (found >= 0) return found;
    }
  }
  return -1;
}

/** Repeats nest one level: one may go at the top or inside a top-level repeat. */
export function canHoldRepeat(nodes: DraftNode[], parentId: string | null): boolean {
  return parentId === null || depthOf(nodes, parentId) === 0;
}

function mapList(nodes: DraftNode[], parentId: string | null, fn: (list: DraftNode[]) => DraftNode[]): DraftNode[] {
  if (parentId === null) return fn(nodes);
  return nodes.map((node) => (node.type === "repeat" ? { ...node, steps: node.id === parentId ? fn(node.steps) : mapList(node.steps, parentId, fn) } : node));
}

/** The list (`null` = top level) that holds `id`. */
function parentOf(nodes: DraftNode[], id: string, parentId: string | null = null): string | null | undefined {
  for (const node of nodes) {
    if (node.id === id) return parentId;
    if (node.type === "repeat") {
      const found = parentOf(node.steps, id, node.id);
      if (found !== undefined) return found;
    }
  }
  return undefined;
}

export function updateNode(nodes: DraftNode[], id: string, fn: (node: DraftNode) => DraftNode): DraftNode[] {
  return nodes.map((node) => {
    if (node.id === id) return fn(node);
    return node.type === "repeat" ? { ...node, steps: updateNode(node.steps, id, fn) } : node;
  });
}

export function appendNode(nodes: DraftNode[], parentId: string | null, node: DraftNode): DraftNode[] {
  return mapList(nodes, parentId, (list) => [...list, node]);
}

export function removeNode(nodes: DraftNode[], id: string): DraftNode[] {
  const parent = parentOf(nodes, id);
  if (parent === undefined) return nodes;
  return mapList(nodes, parent, (list) => list.filter((node) => node.id !== id));
}

export function moveNode(nodes: DraftNode[], id: string, offset: -1 | 1): DraftNode[] {
  const parent = parentOf(nodes, id);
  if (parent === undefined) return nodes;
  return mapList(nodes, parent, (list) => {
    const from = list.findIndex((node) => node.id === id);
    const to = from + offset;
    if (to < 0 || to >= list.length) return list;
    const next = [...list];
    [next[from], next[to]] = [next[to], next[from]];
    return next;
  });
}

function cloneNode(node: DraftNode): DraftNode {
  return node.type === "repeat" ? { ...node, id: nextId(), steps: node.steps.map(cloneNode) } : { ...node, id: nextId() };
}

/** A copy right after the original, with fresh ids. */
export function duplicateNode(nodes: DraftNode[], id: string): DraftNode[] {
  const parent = parentOf(nodes, id);
  if (parent === undefined) return nodes;
  return mapList(nodes, parent, (list) => list.flatMap((node) => (node.id === id ? [node, cloneNode(node)] : [node])));
}

/** Steps plus repeat markers, as a head unit counts them (backend `structure_size`). */
export function structureSize(nodes: DraftNode[]): number {
  return nodes.reduce((total, node) => total + (node.type === "repeat" ? 1 + structureSize(node.steps) : 1), 0);
}

// ---------------------------------------------------------------- validation & payload

function stepErrors(step: DraftStep): StepField[] {
  const errors: StepField[] = [];
  if (step.lengthMode === "time" && !inRange(parseDuration(step.duration), 1, LIMITS.durationS)) errors.push("duration");
  if (step.lengthMode === "distance") {
    const distance = parseNumber(step.distance);
    if (!inRange(distance, Number.MIN_VALUE, LIMITS.distanceM)) errors.push("distance");
  }
  if (step.lengthMode === "laps" && !inRange(parseNumber(step.laps), 1, LIMITS.laps, true)) errors.push("laps");
  if (step.powerUnit !== "") {
    const max = step.powerUnit === "ftp_pct" ? LIMITS.ftpPct : LIMITS.watts;
    const low = parseNumber(step.powerLow);
    const high = parseNumber(step.powerHigh);
    if (!inRange(low, Number.MIN_VALUE, max)) errors.push("powerLow");
    else if (high != null && !inRange(high, low!, max)) errors.push("powerHigh");
  }
  const cadenceLow = parseNumber(step.cadenceLow);
  const cadenceHigh = parseNumber(step.cadenceHigh);
  if (cadenceLow != null || cadenceHigh != null) {
    if (!inRange(cadenceLow, LIMITS.cadence.min, LIMITS.cadence.max, true)) errors.push("cadenceLow");
    else if (cadenceHigh != null && !inRange(cadenceHigh, cadenceLow!, LIMITS.cadence.max, true)) errors.push("cadenceHigh");
  }
  if (step.targetTime.trim() !== "" && (step.eventKey === "" || parseTimeInput(step.targetTime) == null)) errors.push("targetTime");
  const chainring = parseNumber(step.chainring);
  const cog = parseNumber(step.cog);
  if (
    (chainring != null || cog != null) &&
    !(inRange(chainring, LIMITS.chainring.min, LIMITS.chainring.max, true) && inRange(cog, LIMITS.cog.min, LIMITS.cog.max, true))
  )
    errors.push("gear");
  return errors;
}

function collectErrors(nodes: DraftNode[], into: Record<string, StepField[]>) {
  for (const node of nodes) {
    let errors: StepField[];
    if (node.type === "repeat") {
      errors = [];
      if (!inRange(parseNumber(node.count), LIMITS.count.min, LIMITS.count.max, true)) errors.push("count");
      if (node.steps.length === 0 || node.steps.length > LIMITS.stepsPerRepeat) errors.push("empty");
      collectErrors(node.steps, into);
    } else {
      errors = stepErrors(node);
    }
    if (errors.length > 0) into[node.id] = errors;
  }
}

export function draftErrors(draft: WorkoutDraft): DraftErrors {
  const errors: DraftErrors = { nodes: {} };
  if (draft.name.trim() === "") errors.name = true;
  const tags = parseTags(draft.tags);
  if (tags.length > LIMITS.tags || tags.some((tag) => tag.length > LIMITS.tagLength)) errors.tags = true;
  if (draft.steps.length === 0) errors.steps = "empty";
  else if (draft.steps.length > LIMITS.topLevelItems || structureSize(draft.steps) > LIMITS.structureSize) errors.steps = "tooMany";
  collectErrors(draft.steps, errors.nodes);
  return errors;
}

export function hasErrors(errors: DraftErrors): boolean {
  return errors.name === true || errors.tags === true || errors.steps != null || Object.keys(errors.nodes).length > 0;
}

function stepPayload(step: DraftStep): WorkoutStep {
  const number = (text: string) => parseNumber(text);
  const powerHigh = number(step.powerHigh);
  const cadenceLow = number(step.cadenceLow);
  const chainring = number(step.chainring);
  return {
    kind: step.kind,
    label: step.label.trim() || null,
    notes: step.notes.trim() || null,
    duration_s: step.lengthMode === "time" ? parseDuration(step.duration) : null,
    distance_m: step.lengthMode === "distance" ? number(step.distance) : null,
    laps: step.lengthMode === "laps" ? number(step.laps) : null,
    power: step.powerUnit === "" ? null : { unit: step.powerUnit, low: number(step.powerLow)!, high: powerHigh },
    cadence: cadenceLow == null ? null : { low: cadenceLow, high: number(step.cadenceHigh) },
    rpe: step.rpe === "" ? null : Number(step.rpe),
    event_key: step.eventKey || null,
    start_type: step.eventKey ? step.startType || null : null,
    target_time_ms: step.eventKey && step.targetTime.trim() !== "" ? parseTimeInput(step.targetTime) : null,
    gear: chainring == null ? null : { chainring_teeth: chainring, cog_teeth: number(step.cog)! },
  };
}

function nodePayload(node: DraftNode): WorkoutItem {
  if (node.type === "step") return stepPayload(node);
  return { type: "repeat", count: Number(node.count), steps: node.steps.map(nodePayload) as (WorkoutStep | InnerRepeat)[] };
}

/** The steps as the API takes them; null while the tree has a problem. */
export function draftSteps(draft: WorkoutDraft): WorkoutItem[] | null {
  const errors = draftErrors(draft);
  return errors.steps == null && Object.keys(errors.nodes).length === 0 ? draft.steps.map(nodePayload) : null;
}

export function draftPayload(draft: WorkoutDraft): WorkoutWrite | null {
  if (hasErrors(draftErrors(draft))) return null;
  return {
    name: draft.name.trim(),
    description: draft.description.trim() || null,
    tags: parseTags(draft.tags),
    steps: draft.steps.map(nodePayload),
  };
}
