import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { errorMessage } from "../../api/errors";
import { Select, useToast } from "../../components/ui";
import { gearChoices } from "./gear";
import type { Bike } from "./types";
import "./GearPicker.css";

/**
 * Which gear a session or an effort was ridden in. For an effort the empty
 * choice means "the session's"; for a session it means no gear.
 */
export function GearPicker({
  bikes,
  value,
  onChange,
  emptyLabel,
  label,
  pending,
  error,
}: {
  bikes: Bike[];
  value: string | null;
  onChange: (gearId: string | null) => Promise<unknown>;
  emptyLabel: string;
  label: string;
  pending?: boolean;
  error?: unknown;
}) {
  const { t } = useTranslation("equipment");
  const { toast } = useToast();
  const choices = gearChoices(bikes);

  if (choices.length === 0 && value == null) {
    return (
      <p className="gear-picker__empty">
        <Link to="/equipment">{t("picker.addBike")}</Link>
      </p>
    );
  }

  return (
    <div className="gear-picker">
      <Select
        label={label}
        scale="sm"
        value={value ?? ""}
        disabled={pending}
        error={error ? errorMessage(error) : undefined}
        onChange={(e) => {
          const next = e.target.value || null;
          onChange(next).then(
            () => toast({ title: t("picker.saved"), tone: "success" }),
            () => undefined, // shown under the field
          );
        }}
      >
        <option value="">{emptyLabel}</option>
        {choices.map((choice) => (
          <option key={choice.id} value={choice.id}>
            {choice.label}
          </option>
        ))}
      </Select>
    </div>
  );
}
