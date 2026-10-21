import { useTranslation } from "react-i18next";
import { Select } from "../../components/ui";
import { rolloutPresetOf } from "./gear";
import { ROLLOUT_PRESETS } from "./types";

/**
 * A standard tire's rollout, "700×25c (2105 mm)", writing its value into the
 * rollout field next to it; shows "Custom" while the typed value is none of them.
 */
export function RolloutPresetSelect({ rolloutMm, onChange }: { rolloutMm: number | null; onChange: (rolloutMm: number) => void }) {
  const { t } = useTranslation("equipment");
  const preset = rolloutPresetOf(rolloutMm);
  return (
    <Select
      label={t("rolloutPreset.label")}
      value={preset?.tire ?? ""}
      onChange={(event) => {
        const picked = ROLLOUT_PRESETS.find((candidate) => candidate.tire === event.target.value);
        if (picked) onChange(picked.rolloutMm);
      }}
    >
      <option value="" disabled>
        {t("rolloutPreset.custom")}
      </option>
      {ROLLOUT_PRESETS.map((candidate) => (
        <option key={candidate.tire} value={candidate.tire}>
          {t("rolloutPreset.option", { tire: candidate.tire, mm: candidate.rolloutMm })}
        </option>
      ))}
    </Select>
  );
}
