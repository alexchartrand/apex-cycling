import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Button, Checkbox, Dialog, Input, Select, useToast } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import {
  formFromTrack,
  invalidFields,
  payloadFromForm,
  TRACK_BOUNDS,
  withHidden,
  type IndoorChoice,
} from "./trackSettingsForm";
import type { TrackSummary } from "./types";
import { useUpdateTrack } from "./useTraining";
import "./TrackSettingsDialog.css";

const INDOOR_CHOICES: IndoorChoice[] = ["unknown", "indoor", "outdoor"];

export function TrackSettingsDialog({
  track,
  open,
  onOpenChange,
}: {
  track: TrackSummary;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useTranslation("training");
  const { t: tc } = useTranslation("common");
  const fmt = useFormat();
  const { toast } = useToast();
  const update = useUpdateTrack(track.id);
  const [form, setForm] = useState(() => formFromTrack(track));
  const invalid = invalidFields(form);

  // Start from the saved settings every time the dialog opens, not from a
  // previous half-finished edit.
  function handleOpenChange(next: boolean) {
    if (next) {
      setForm(formFromTrack(track));
      update.reset();
    }
    onOpenChange(next);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (invalid.size > 0) return;
    try {
      await update.mutateAsync(payloadFromForm(form));
      toast({ title: t("trackSettings.saved"), tone: "success" });
      onOpenChange(false);
    } catch {
      // surfaced via update.error below
    }
  }

  const numberField = (key: "length" | "elevation" | "temperature", label: string, suffix: string, hint?: string) => (
    <Input
      label={label}
      type="number"
      inputMode="decimal"
      suffix={suffix}
      hint={hint}
      error={invalid.has(key) ? t("trackSettings.outOfRange", TRACK_BOUNDS[key]) : undefined}
      value={form[key]}
      onChange={(e) => setForm({ ...form, [key]: e.target.value })}
      min={TRACK_BOUNDS[key].min}
      max={TRACK_BOUNDS[key].max}
      step={TRACK_BOUNDS[key].step}
    />
  );

  return (
    <Dialog
      open={open}
      onOpenChange={handleOpenChange}
      title={t("trackSettings.title", { name: track.name })}
      description={t("trackSettings.description")}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={() => handleOpenChange(false)}>
            {tc("cancel")}
          </Button>
          <Button type="submit" form="track-settings-form" loading={update.isPending} disabled={invalid.size > 0}>
            {tc("save")}
          </Button>
        </>
      }
    >
      <form id="track-settings-form" className="track-settings" onSubmit={handleSubmit}>
        <div className="track-settings__facts">
          {numberField("length", t("trackSettings.length"), tc("units.m"), t("trackSettings.lengthHint"))}
          <Select
            label={t("trackSettings.indoor")}
            value={form.indoor}
            onChange={(e) => setForm({ ...form, indoor: e.target.value as IndoorChoice })}
          >
            {INDOOR_CHOICES.map((choice) => (
              <option key={choice} value={choice}>
                {t(`trackSettings.indoorChoices.${choice}`)}
              </option>
            ))}
          </Select>
          {numberField("elevation", t("trackSettings.elevation"), tc("units.m"), t("trackSettings.elevationHint"))}
          {numberField("temperature", t("trackSettings.temperature"), "°C", t("trackSettings.temperatureHint"))}
        </div>

        <fieldset className="track-settings__group">
          <legend>{t("trackSettings.loops")}</legend>
          <p className="track-settings__hint">{t("trackSettings.loopsHint")}</p>
          <div className="track-settings__checks">
            {track.loops.map((loop) => (
              <Checkbox
                key={loop.id}
                label={loop.distance_m != null ? `${loop.name} · ${fmt.distance(loop.distance_m)}` : loop.name}
                checked={!form.hiddenLoopIds.includes(loop.id)}
                onChange={(e) => setForm({ ...form, hiddenLoopIds: withHidden(form.hiddenLoopIds, loop.id, !e.target.checked) })}
              />
            ))}
          </div>
        </fieldset>

        {track.views.length > 0 && (
          <fieldset className="track-settings__group">
            <legend>{t("trackSettings.views")}</legend>
            <p className="track-settings__hint">{t("trackSettings.viewsHint")}</p>
            <div className="track-settings__checks">
              {track.views.map((view) => (
                <Checkbox
                  key={view.id}
                  label={view.name}
                  checked={!form.hiddenViewIds.includes(view.id)}
                  onChange={(e) => setForm({ ...form, hiddenViewIds: withHidden(form.hiddenViewIds, view.id, !e.target.checked) })}
                />
              ))}
            </div>
          </fieldset>
        )}

        {update.isError && (
          <p className="track-settings__error" role="alert">
            {errorMessage(update.error, { 403: t("trackSettings.forbidden") })}
          </p>
        )}
      </form>
    </Dialog>
  );
}
