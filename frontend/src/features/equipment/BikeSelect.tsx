import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Select } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import type { Bike } from "./types";

/**
 * One of the athlete's bikes, "Track bike (7.2 kg)". The empty choice is
 * whatever applies without one (`emptyLabel`); with `emptyDisabled` it only
 * labels a value no bike matches. Nothing shows while there is no bike to pick.
 */
export function BikeSelect({
  bikes,
  value,
  onChange,
  label,
  emptyLabel,
  hint,
  emptyDisabled,
}: {
  bikes: Bike[];
  value: string | null;
  onChange: (bike: Bike | null) => void;
  label?: ReactNode;
  emptyLabel: string;
  hint?: ReactNode;
  emptyDisabled?: boolean;
}) {
  const { t } = useTranslation("equipment");
  const fmt = useFormat();
  if (bikes.length === 0) return null;
  return (
    <Select
      label={label ?? t("bikeSelect.label")}
      hint={hint}
      value={value ?? ""}
      onChange={(event) => onChange(bikes.find((bike) => bike.id === event.target.value) ?? null)}
    >
      <option value="" disabled={emptyDisabled}>
        {emptyLabel}
      </option>
      {bikes.map((bike) => (
        <option key={bike.id} value={bike.id}>
          {bike.weight_kg != null ? t("bikeSelect.withWeight", { name: bike.name, weight: fmt.number(bike.weight_kg, 1) }) : bike.name}
        </option>
      ))}
    </Select>
  );
}
