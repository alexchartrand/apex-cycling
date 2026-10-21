import { Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Button, Dialog, IconButton, Input, Select, Textarea, useToast } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { gearChoices } from "../equipment/gear";
import { useBikes } from "../equipment/useEquipment";
import { EVENT_START_TYPES, STANDARD_EVENT_KEYS, type StandardEventKey } from "../records/types";
import { emptyEffortRow, emptyPlanForm, planFormErrors, planFormFrom, planPayload, withRowEvent, type EffortRow, type PlanForm } from "./planForm";
import type { PlannedSession } from "./types";
import { useSavePlan } from "./usePlan";
import "./Plan.css";

/** Plan a session on `date`, or edit `plan`. Remount it (key) per plan so its fields start fresh. */
export function PlanDialog({ athleteId, date, plan, onClose }: { athleteId: string; date: string; plan: PlannedSession | null; onClose: () => void }) {
  const { t } = useTranslation("plan");
  const { t: tr } = useTranslation("records");
  const { t: tc } = useTranslation("common");
  const fmt = useFormat();
  const { toast } = useToast();
  const save = useSavePlan(athleteId);
  const gears = gearChoices(useBikes(athleteId).data ?? []);
  const [form, setForm] = useState<PlanForm>(() => (plan ? planFormFrom(plan, fmt) : emptyPlanForm(date)));
  const [showErrors, setShowErrors] = useState(false);
  const errors = planFormErrors(form);
  const set = <K extends keyof PlanForm>(key: K, value: PlanForm[K]) => setForm((current) => ({ ...current, [key]: value }));
  const setRow = (index: number, row: EffortRow) => set("targets", form.targets.map((existing, i) => (i === index ? row : existing)));

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const payload = planPayload(form);
    if (!payload) {
      setShowErrors(true);
      return;
    }
    try {
      await save.mutateAsync({ planId: plan?.id, payload });
      toast({ title: t("saved"), tone: "success" });
      onClose();
    } catch {
      // shown in the form
    }
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={plan ? t("dialog.editTitle") : t("dialog.addTitle")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {tc("cancel")}
          </Button>
          <Button type="submit" form="plan-form" loading={save.isPending}>
            {tc("save")}
          </Button>
        </>
      }
    >
      <form id="plan-form" className="plan-form" onSubmit={handleSubmit} noValidate>
        <div className="plan-form__row plan-form__row--title">
          <Input
            label={t("dialog.title")}
            value={form.title}
            maxLength={120}
            placeholder={t("dialog.titlePlaceholder")}
            error={showErrors && errors.title ? t("dialog.titleRequired") : undefined}
            onChange={(e) => set("title", e.target.value)}
            autoFocus={!plan}
          />
          <Input
            label={t("dialog.date")}
            type="date"
            value={form.date}
            error={showErrors && errors.date ? t("dialog.dateInvalid") : undefined}
            onChange={(e) => set("date", e.target.value)}
            required
          />
        </div>
        <Textarea label={t("dialog.description")} rows={3} maxLength={5000} value={form.description} onChange={(e) => set("description", e.target.value)} />

        <fieldset className="plan-form__targets">
          <legend>{t("dialog.targets")}</legend>
          <p className="plan-form__hint">{t("dialog.targetsHint")}</p>
          {form.targets.map((row, index) => {
            const problem = showErrors ? errors.targets[index] : undefined;
            return (
              <div key={index} className="plan-form__target">
                <Input
                  label={t("dialog.label")}
                  value={row.label}
                  maxLength={100}
                  placeholder={t("dialog.labelPlaceholder")}
                  error={problem === "label" ? t("dialog.labelRequired") : undefined}
                  onChange={(e) => setRow(index, { ...row, label: e.target.value })}
                />
                <Input
                  label={t("dialog.reps")}
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={99}
                  value={row.reps}
                  error={problem === "reps" ? t("dialog.repsInvalid") : undefined}
                  onChange={(e) => setRow(index, { ...row, reps: e.target.value })}
                />
                <Select label={t("dialog.event")} value={row.eventKey} onChange={(e) => setRow(index, withRowEvent(row, e.target.value as "" | StandardEventKey))}>
                  <option value="">{t("dialog.noEvent")}</option>
                  {STANDARD_EVENT_KEYS.map((key) => (
                    <option key={key} value={key}>
                      {tr(`events.${key}`)}
                    </option>
                  ))}
                </Select>
                <Select
                  label={t("dialog.start")}
                  value={row.startType}
                  disabled={row.eventKey === ""}
                  onChange={(e) => setRow(index, { ...row, startType: e.target.value as EffortRow["startType"] })}
                >
                  <option value="">{t("dialog.anyStart")}</option>
                  {(row.eventKey ? EVENT_START_TYPES[row.eventKey] : []).map((start) => (
                    <option key={start} value={start}>
                      {tr(`startTypes.${start}`)}
                    </option>
                  ))}
                </Select>
                <Input
                  label={t("dialog.time")}
                  value={row.time}
                  inputMode="decimal"
                  autoComplete="off"
                  disabled={row.eventKey === ""}
                  placeholder="34.0"
                  error={problem === "time" ? t("dialog.timeInvalid") : undefined}
                  onChange={(e) => setRow(index, { ...row, time: e.target.value })}
                />
                {gears.length > 0 && (
                  <div className="plan-form__gear">
                    <Select label={t("dialog.gear")} value={row.gearId} onChange={(e) => setRow(index, { ...row, gearId: e.target.value })}>
                      <option value="">{t("dialog.anyGear")}</option>
                      {gears.map((gear) => (
                        <option key={gear.id} value={gear.id}>
                          {gear.label}
                        </option>
                      ))}
                    </Select>
                  </div>
                )}
                <IconButton
                  aria-label={t("dialog.removeBlock", { n: index + 1 })}
                  className="plan-form__remove"
                  onClick={() => set("targets", form.targets.filter((_, i) => i !== index))}
                >
                  <Trash2 aria-hidden />
                </IconButton>
              </div>
            );
          })}
          <Button size="sm" variant="secondary" icon={<Plus aria-hidden />} onClick={() => set("targets", [...form.targets, emptyEffortRow()])} disabled={form.targets.length >= 30}>
            {t("dialog.addBlock")}
          </Button>
        </fieldset>

        {save.isError && (
          <p className="plan-form__error" role="alert">
            {errorMessage(save.error)}
          </p>
        )}
      </form>
    </Dialog>
  );
}
