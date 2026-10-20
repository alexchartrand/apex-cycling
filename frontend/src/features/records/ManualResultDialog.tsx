import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Button, Checkbox, Dialog, Input, Select, Textarea, useToast } from "../../components/ui";
import { localIsoDate } from "../../i18n/format";
import { useFormat } from "../../i18n/useFormat";
import type { TrackSummary } from "../training/types";
import { emptyManualForm, manualFormErrors, manualFormFrom, manualPayload, withEvent, type ManualForm } from "./manualForm";
import { EVENT_START_TYPES, STANDARD_EVENT_KEYS, type ManualResult, type StandardEventKey } from "./types";
import { useCreateManualResult, useUpdateManualResult } from "./useRecords";

/** Add a result, or edit `result` when given. Remount it (key) per result so its fields start fresh. */
export function ManualResultDialog({
  athleteId,
  tracks,
  result,
  onClose,
}: {
  athleteId: string;
  tracks: TrackSummary[];
  result: ManualResult | null;
  onClose: () => void;
}) {
  const { t } = useTranslation("records");
  const { t: tc } = useTranslation("common");
  const fmt = useFormat();
  const { toast } = useToast();
  const create = useCreateManualResult(athleteId);
  const update = useUpdateManualResult(athleteId);
  const mutation = result ? update : create;
  const [form, setForm] = useState<ManualForm>(() =>
    result ? manualFormFrom(result, fmt) : emptyManualForm(localIsoDate(), tracks[0]?.id ?? null),
  );
  const [showErrors, setShowErrors] = useState(false);
  const errors = manualFormErrors(form);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const payload = manualPayload(form);
    if (!payload) {
      setShowErrors(true);
      return;
    }
    try {
      if (result) await update.mutateAsync({ id: result.id, payload });
      else await create.mutateAsync(payload);
      toast({ title: t("manual.saved"), tone: "success" });
      onClose();
    } catch {
      // shown in the form
    }
  }

  const set = <K extends keyof ManualForm>(key: K, value: ManualForm[K]) => setForm((current) => ({ ...current, [key]: value }));

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={result ? t("manual.dialogEditTitle") : t("manual.dialogAddTitle")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {tc("cancel")}
          </Button>
          <Button type="submit" form="manual-result-form" loading={mutation.isPending}>
            {tc("save")}
          </Button>
        </>
      }
    >
      <form id="manual-result-form" className="manual-form" onSubmit={handleSubmit} noValidate>
        <div className="manual-form__row">
          <Select label={t("manual.event")} value={form.eventKey} onChange={(e) => setForm(withEvent(form, e.target.value as StandardEventKey))}>
            {STANDARD_EVENT_KEYS.map((key) => (
              <option key={key} value={key}>
                {t(`events.${key}`)}
              </option>
            ))}
          </Select>
          <Select
            label={t("manual.start")}
            value={form.startType}
            onChange={(e) => set("startType", e.target.value as ManualForm["startType"])}
            disabled={EVENT_START_TYPES[form.eventKey].length === 1}
          >
            {EVENT_START_TYPES[form.eventKey].map((start) => (
              <option key={start} value={start}>
                {t(`startTypes.${start}`)}
              </option>
            ))}
          </Select>
        </div>
        <div className="manual-form__row">
          <Input
            label={t("manual.time")}
            value={form.time}
            inputMode="decimal"
            autoComplete="off"
            hint={t("manual.timeHint")}
            error={showErrors && errors.time ? t("manual.timeInvalid") : undefined}
            onChange={(e) => set("time", e.target.value)}
            autoFocus={!result}
          />
          <Input label={t("manual.date")} type="date" value={form.date} max={localIsoDate()} onChange={(e) => set("date", e.target.value)} required />
        </div>
        <Select
          label={t("manual.placeField")}
          value={form.placeKind === "track" ? form.trackId : "__venue__"}
          onChange={(e) => {
            if (e.target.value === "__venue__") setForm({ ...form, placeKind: "venue" });
            else setForm({ ...form, placeKind: "track", trackId: e.target.value });
          }}
        >
          {tracks.map((track) => (
            <option key={track.id} value={track.id}>
              {track.name}
            </option>
          ))}
          <option value="__venue__">{t("manual.placeVenue")}</option>
        </Select>
        {form.placeKind === "venue" && (
          <Input
            label={t("manual.venue")}
            value={form.venue}
            maxLength={255}
            placeholder={t("manual.venuePlaceholder")}
            error={showErrors && errors.place ? t("manual.venueRequired") : undefined}
            onChange={(e) => set("venue", e.target.value)}
          />
        )}
        <Checkbox label={t("manual.competition")} checked={form.competition} onChange={(e) => set("competition", e.target.checked)} />
        <Textarea label={t("manual.notes")} rows={3} maxLength={1000} value={form.notes} onChange={(e) => set("notes", e.target.value)} />
        {mutation.isError && (
          <p className="manual-form__error" role="alert">
            {errorMessage(mutation.error)}
          </p>
        )}
      </form>
    </Dialog>
  );
}
