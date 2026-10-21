import { useTranslation } from "react-i18next";
import { Select } from "../../components/ui";
import { STANDARD_TIRES, standardTireOf, tiresByBrand } from "./gear";
import type { StandardTire } from "./types";

/**
 * A listed tire, grouped by brand ("Pista Control · tubular · 23 mm" under
 * Vittoria), writing its full label and Crr into the fields next to it; shows "Other" while
 * the typed values are none of them.
 */
export function TireSelect({ name, crr, onChange }: { name: string; crr: number | null; onChange: (tire: StandardTire) => void }) {
  const { t } = useTranslation("equipment");
  const current = standardTireOf(name, crr);
  return (
    <Select
      label={t("tireSelect.label")}
      value={current?.label ?? ""}
      onChange={(event) => {
        const picked = STANDARD_TIRES.find((tire) => tire.label === event.target.value);
        if (picked) onChange(picked);
      }}
    >
      <option value="" disabled>
        {t("tireSelect.other")}
      </option>
      {tiresByBrand().map(([brand, tires]) => (
        <optgroup key={brand} label={brand}>
          {tires.map((tire) => (
            <option key={tire.label} value={tire.label}>
              {t("tireSelect.option", { name: tire.name, type: tire.type, size: tire.size })}
            </option>
          ))}
        </optgroup>
      ))}
    </Select>
  );
}
