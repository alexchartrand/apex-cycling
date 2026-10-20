import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Card, Input, SegmentedControl, Select } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { NUMBER_FIELDS, type NumberKey, type NumberSpec, type StartKind, START_PARAM } from "./toolInputs";
import type { ToolInputs } from "./useToolInputs";

export function NumberField({
  inputs,
  name,
  label,
  suffix,
  hint,
}: {
  inputs: ToolInputs;
  name: NumberKey;
  label: ReactNode;
  suffix?: ReactNode;
  hint?: ReactNode;
}) {
  const { t } = useTranslation("tools");
  const fmt = useFormat();
  const state = inputs.field(name);
  const spec: NumberSpec = NUMBER_FIELDS[name];
  const error = state.invalid
    ? t(spec.integer ? "errors.integer" : "errors.range", { min: fmt.number(spec.min, 4), max: fmt.number(spec.max, 4) })
    : undefined;
  return (
    <Input
      label={label}
      suffix={suffix}
      hint={hint}
      error={error}
      inputMode={spec.min < 0 ? "text" : "decimal"}
      autoComplete="off"
      value={state.raw}
      onChange={(event) => inputs.set(name, event.target.value)}
    />
  );
}

export function StartControl({ inputs }: { inputs: ToolInputs }) {
  const { t } = useTranslation("tools");
  return (
    <div className="field">
      <span className="field__label">{t("effort.start")}</span>
      <SegmentedControl<StartKind>
        aria-label={t("effort.start")}
        value={inputs.start}
        onChange={(value) => inputs.setParam(START_PARAM, value)}
        options={[
          { value: "standing", label: t("effort.standing") },
          { value: "flying", label: t("effort.flying") },
        ]}
      />
    </div>
  );
}

export function RiderCard({ inputs }: { inputs: ToolInputs }) {
  const { t } = useTranslation("tools");
  const { t: tc } = useTranslation("common");
  return (
    <Card title={t("rider.title")} as="section">
      <div className="tools-grid">
        <NumberField
          inputs={inputs}
          name="riderKg"
          label={t("rider.riderKg")}
          suffix={tc("units.kg")}
          hint={inputs.weightFromProfile ? t("rider.fromProfile") : undefined}
        />
        <NumberField inputs={inputs} name="bikeKg" label={t("rider.bikeKg")} suffix={tc("units.kg")} />
        <NumberField inputs={inputs} name="cda" label={t("rider.cda")} suffix="m²" hint={t("rider.cdaHint")} />
        <NumberField inputs={inputs} name="crr" label={t("rider.crr")} hint={t("rider.crrHint")} />
        <NumberField inputs={inputs} name="efficiencyPct" label={t("rider.efficiency")} suffix="%" />
      </div>
    </Card>
  );
}

export function TrackSelect({ inputs }: { inputs: ToolInputs }) {
  const { t } = useTranslation("tools");
  const fmt = useFormat();
  if (inputs.tracks.length === 0) return null;
  return (
    <Select
      label={t("air.track")}
      hint={t("air.trackHint")}
      value={inputs.track?.id ?? ""}
      onChange={(event) => inputs.setTrack(event.target.value)}
    >
      <option value="">{t("air.noTrack")}</option>
      {inputs.tracks.map((track) => (
        <option key={track.id} value={track.id}>
          {track.length_m != null ? `${track.name} (${fmt.distance(track.length_m)})` : track.name}
        </option>
      ))}
    </Select>
  );
}

/** Track + air inputs; `children` adds tool-specific fields (lap length…). */
export function ConditionsCard({ inputs, children }: { inputs: ToolInputs; children?: ReactNode }) {
  const { t } = useTranslation("tools");
  const fmt = useFormat();
  return (
    <Card
      title={t("air.title")}
      as="section"
      actions={
        inputs.rho !== null && (
          <span className="tools-rho">{t("air.rhoValue", { value: fmt.number(inputs.rho, 4, 4) })}</span>
        )
      }
    >
      <div className="tools-grid">
        <TrackSelect inputs={inputs} />
        {children}
        <NumberField inputs={inputs} name="tempC" label={t("air.temp")} suffix="°C" />
        <NumberField inputs={inputs} name="elevationM" label={t("air.elevation")} suffix="m" />
        <NumberField inputs={inputs} name="humidityPct" label={t("air.humidity")} suffix="%" />
        <NumberField inputs={inputs} name="pressureHpa" label={t("air.pressure")} suffix="hPa" hint={t("air.pressureHint")} />
      </div>
    </Card>
  );
}
