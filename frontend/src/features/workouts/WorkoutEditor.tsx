import { ArrowDown, ArrowUp, Copy, Plus, Repeat, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, IconButton, Input, Select, Textarea } from "../../components/ui";
import { EVENT_START_TYPES, STANDARD_EVENT_KEYS, type StandardEventKey } from "../records/types";
import { STEP_KINDS, type StepKind } from "./types";
import {
  LIMITS,
  appendNode,
  canHoldRepeat,
  duplicateNode,
  moveNode,
  newRepeat,
  newStep,
  removeNode,
  updateNode,
  withEvent,
  type DraftNode,
  type DraftRepeat,
  type DraftStep,
  type LengthMode,
  type StepField,
} from "./workoutDraft";

type Change = (fn: (nodes: DraftNode[]) => DraftNode[]) => void;
type Shared = { root: DraftNode[]; change: Change; errors: Record<string, StepField[]> | null };

/** The step tree as editable cards; `errors` is null until the user tries to save. */
export function WorkoutEditor({
  steps,
  onChange,
  errors,
}: {
  steps: DraftNode[];
  onChange: (steps: DraftNode[]) => void;
  errors: Record<string, StepField[]> | null;
}) {
  const shared: Shared = { root: steps, change: (fn) => onChange(fn(steps)), errors };
  return <NodeList nodes={steps} parentId={null} shared={shared} />;
}

function NodeList({ nodes, parentId, shared }: { nodes: DraftNode[]; parentId: string | null; shared: Shared }) {
  const { t } = useTranslation("workouts");
  const full = nodes.length >= (parentId === null ? LIMITS.topLevelItems : LIMITS.stepsPerRepeat);
  return (
    <div className="workout-editor__list">
      {nodes.map((node, index) => (
        <div key={node.id} className="workout-editor__item">
          {node.type === "repeat" ? (
            <RepeatCard block={node} shared={shared} first={index === 0} last={index === nodes.length - 1} />
          ) : (
            <StepCard step={node} shared={shared} first={index === 0} last={index === nodes.length - 1} />
          )}
        </div>
      ))}
      <div className="workout-editor__add">
        <Button size="sm" variant="secondary" icon={<Plus aria-hidden />} disabled={full} onClick={() => shared.change((root) => appendNode(root, parentId, newStep()))}>
          {t("editor.addStep")}
        </Button>
        {canHoldRepeat(shared.root, parentId) && (
          <Button size="sm" variant="ghost" icon={<Repeat aria-hidden />} disabled={full} onClick={() => shared.change((root) => appendNode(root, parentId, newRepeat()))}>
            {t("editor.addRepeat")}
          </Button>
        )}
      </div>
    </div>
  );
}

function NodeActions({ id, name, shared, first, last }: { id: string; name: string; shared: Shared; first: boolean; last: boolean }) {
  const { t } = useTranslation("workouts");
  return (
    <div className="workout-editor__actions">
      <IconButton size="sm" aria-label={t("editor.moveUp", { name })} disabled={first} onClick={() => shared.change((root) => moveNode(root, id, -1))}>
        <ArrowUp aria-hidden />
      </IconButton>
      <IconButton size="sm" aria-label={t("editor.moveDown", { name })} disabled={last} onClick={() => shared.change((root) => moveNode(root, id, 1))}>
        <ArrowDown aria-hidden />
      </IconButton>
      <IconButton size="sm" aria-label={t("editor.duplicate", { name })} onClick={() => shared.change((root) => duplicateNode(root, id))}>
        <Copy aria-hidden />
      </IconButton>
      <IconButton size="sm" aria-label={t("editor.remove", { name })} onClick={() => shared.change((root) => removeNode(root, id))}>
        <Trash2 aria-hidden />
      </IconButton>
    </div>
  );
}

function RepeatCard({ block, shared, first, last }: { block: DraftRepeat; shared: Shared; first: boolean; last: boolean }) {
  const { t } = useTranslation("workouts");
  const errors = shared.errors?.[block.id] ?? [];
  const name = t("editor.repeatName");
  return (
    <section className="workout-editor__repeat" aria-label={name}>
      <header className="workout-editor__header">
        <Repeat aria-hidden className="workout-editor__repeat-icon" />
        <Input
          className="workout-editor__count"
          aria-label={t("editor.count")}
          type="number"
          inputMode="numeric"
          min={LIMITS.count.min}
          max={LIMITS.count.max}
          value={block.count}
          error={errors.includes("count") ? t("editor.errors.count") : undefined}
          onChange={(e) => shared.change((root) => updateNode(root, block.id, (node) => ({ ...(node as DraftRepeat), count: e.target.value })))}
        />
        <span className="workout-editor__repeat-title">× {name}</span>
        <NodeActions id={block.id} name={name} shared={shared} first={first} last={last} />
      </header>
      {errors.includes("empty") && (
        <p className="workout-editor__error" role="alert">
          {t("editor.errors.empty")}
        </p>
      )}
      <NodeList nodes={block.steps} parentId={block.id} shared={shared} />
    </section>
  );
}

function StepCard({ step, shared, first, last }: { step: DraftStep; shared: Shared; first: boolean; last: boolean }) {
  const { t } = useTranslation("workouts");
  const { t: tr } = useTranslation("records");
  const [showTrack, setShowTrack] = useState(step.eventKey !== "" || step.chainring !== "" || step.cog !== "");
  const [showNotes, setShowNotes] = useState(step.notes !== "");
  const errors = shared.errors?.[step.id] ?? [];
  const error = (field: StepField) => (errors.includes(field) ? t(`editor.errors.${field}`) : undefined);
  const set = (patch: Partial<DraftStep>) => shared.change((root) => updateNode(root, step.id, (node) => ({ ...(node as DraftStep), ...patch })));
  const name = step.label.trim() || t(`kinds.${step.kind}`);
  const powerSuffix = step.powerUnit === "watts" ? t("units.w") : "%";

  return (
    <section className={`workout-editor__step workout-editor__step--${step.kind}`} aria-label={name}>
      <header className="workout-editor__header">
        <Select className="workout-editor__kind" aria-label={t("editor.kind")} value={step.kind} onChange={(e) => set({ kind: e.target.value as StepKind })}>
          {STEP_KINDS.map((kind) => (
            <option key={kind} value={kind}>
              {t(`kinds.${kind}`)}
            </option>
          ))}
        </Select>
        <Input
          className="workout-editor__label"
          aria-label={t("editor.label")}
          placeholder={t(`kinds.${step.kind}`)}
          maxLength={100}
          value={step.label}
          onChange={(e) => set({ label: e.target.value })}
        />
        <NodeActions id={step.id} name={name} shared={shared} first={first} last={last} />
      </header>

      <div className="workout-editor__fields">
        <div className="workout-editor__group">
          <Select label={t("editor.length")} value={step.lengthMode} onChange={(e) => set({ lengthMode: e.target.value as LengthMode })}>
            <option value="time">{t("editor.lengthModes.time")}</option>
            <option value="distance">{t("editor.lengthModes.distance")}</option>
            <option value="laps">{t("editor.lengthModes.laps")}</option>
            <option value="open">{step.eventKey ? t("editor.lengthModes.event") : t("editor.lengthModes.open")}</option>
          </Select>
          {step.lengthMode === "time" && (
            <Input
              label={t("editor.duration")}
              inputMode="numeric"
              autoComplete="off"
              placeholder="5:00"
              value={step.duration}
              error={error("duration")}
              onChange={(e) => set({ duration: e.target.value })}
            />
          )}
          {step.lengthMode === "distance" && (
            <Input
              label={t("editor.distance")}
              inputMode="decimal"
              suffix="m"
              value={step.distance}
              error={error("distance")}
              onChange={(e) => set({ distance: e.target.value })}
            />
          )}
          {step.lengthMode === "laps" && (
            <Input label={t("editor.laps")} type="number" inputMode="numeric" min={1} max={LIMITS.laps} value={step.laps} error={error("laps")} onChange={(e) => set({ laps: e.target.value })} />
          )}
        </div>

        <div className="workout-editor__group">
          <Select label={t("editor.power")} value={step.powerUnit} onChange={(e) => set({ powerUnit: e.target.value as DraftStep["powerUnit"] })}>
            <option value="">{t("editor.noPower")}</option>
            <option value="ftp_pct">{t("units.ftpPct")}</option>
            <option value="watts">{t("units.w")}</option>
          </Select>
          {step.powerUnit !== "" && (
            <>
              <Input label={t("editor.from")} inputMode="decimal" suffix={powerSuffix} value={step.powerLow} error={error("powerLow")} onChange={(e) => set({ powerLow: e.target.value })} />
              <Input
                label={t("editor.to")}
                inputMode="decimal"
                suffix={powerSuffix}
                placeholder={t("editor.optional")}
                value={step.powerHigh}
                error={error("powerHigh")}
                onChange={(e) => set({ powerHigh: e.target.value })}
              />
            </>
          )}
        </div>

        <div className="workout-editor__group">
          <Input
            label={t("editor.cadence")}
            inputMode="numeric"
            suffix={t("units.rpm")}
            value={step.cadenceLow}
            error={error("cadenceLow")}
            onChange={(e) => set({ cadenceLow: e.target.value })}
          />
          <Input
            label={t("editor.to")}
            inputMode="numeric"
            suffix={t("units.rpm")}
            placeholder={t("editor.optional")}
            value={step.cadenceHigh}
            error={error("cadenceHigh")}
            onChange={(e) => set({ cadenceHigh: e.target.value })}
          />
          <Select label={t("editor.rpe")} value={step.rpe} onChange={(e) => set({ rpe: e.target.value })}>
            <option value="">{t("editor.noRpe")}</option>
            {Array.from({ length: 10 }, (_, i) => String(i + 1)).map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </Select>
        </div>

        {showTrack ? (
          <div className="workout-editor__group workout-editor__group--track">
            <Select label={t("editor.event")} value={step.eventKey} onChange={(e) => set(withEvent(step, e.target.value as "" | StandardEventKey))}>
              <option value="">{t("editor.noEvent")}</option>
              {STANDARD_EVENT_KEYS.map((key) => (
                <option key={key} value={key}>
                  {tr(`events.${key}`)}
                </option>
              ))}
            </Select>
            <Select
              label={t("editor.start")}
              value={step.startType}
              disabled={step.eventKey === ""}
              onChange={(e) => set({ startType: e.target.value as DraftStep["startType"] })}
            >
              <option value="">{t("editor.anyStart")}</option>
              {(step.eventKey ? EVENT_START_TYPES[step.eventKey] : []).map((start) => (
                <option key={start} value={start}>
                  {tr(`startTypes.${start}`)}
                </option>
              ))}
            </Select>
            <Input
              label={t("editor.targetTime")}
              inputMode="decimal"
              autoComplete="off"
              placeholder="11.5"
              disabled={step.eventKey === ""}
              value={step.targetTime}
              error={error("targetTime")}
              onChange={(e) => set({ targetTime: e.target.value })}
            />
            <div className="workout-editor__gear">
              <Input label={t("editor.chainring")} type="number" inputMode="numeric" value={step.chainring} error={error("gear")} onChange={(e) => set({ chainring: e.target.value })} />
              <span aria-hidden>×</span>
              <Input label={t("editor.cog")} type="number" inputMode="numeric" value={step.cog} onChange={(e) => set({ cog: e.target.value })} />
            </div>
          </div>
        ) : null}

        {showNotes && (
          <Textarea label={t("editor.notes")} rows={2} maxLength={500} value={step.notes} onChange={(e) => set({ notes: e.target.value })} />
        )}

        {(!showTrack || !showNotes) && (
          <div className="workout-editor__more">
            {!showTrack && (
              <Button size="sm" variant="ghost" icon={<Plus aria-hidden />} onClick={() => setShowTrack(true)}>
                {t("editor.addTrack")}
              </Button>
            )}
            {!showNotes && (
              <Button size="sm" variant="ghost" icon={<Plus aria-hidden />} onClick={() => setShowNotes(true)}>
                {t("editor.addNotes")}
              </Button>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
