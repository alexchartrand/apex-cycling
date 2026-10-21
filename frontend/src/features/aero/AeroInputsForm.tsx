import { useTranslation } from "react-i18next";
import { Input } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { BikeSelect } from "../equipment/BikeSelect";
import { bikeOfWeight, weighedBikes } from "../equipment/gear";
import type { Bike } from "../equipment/types";
import { INPUT_BOUNDS, INPUT_KEYS, readInputs, type InputDraft, type InputKey } from "./aero";
import type { AeroConditions } from "./types";

const SUFFIX: Record<InputKey, string | undefined> = {
  temp_c: "°C",
  elevation_m: "m",
  pressure_hpa: "hPa",
  humidity_pct: "%",
  rider_kg: "kg",
  bike_kg: "kg",
  crr: undefined,
};

/**
 * The estimate's assumptions; a blank field shows, as its placeholder, the
 * value the estimate used. Picking a bike types its weight in; the blank
 * choice is the bike of the session's gear (else the default).
 */
export function AeroInputsForm({
  draft,
  invalid,
  conditions,
  crrUsed,
  bikes,
  onChange,
}: {
  draft: InputDraft;
  invalid: InputKey[];
  conditions: AeroConditions | null;
  crrUsed: number | null;
  bikes: Bike[];
  onChange: (key: InputKey, value: string) => void;
}) {
  const { t } = useTranslation("aero");
  const fmt = useFormat();

  const placeholder = (key: InputKey): string => {
    if (!conditions) return "";
    if (key === "pressure_hpa") return t("inputs.pressureFromElevation");
    if (key === "crr") return crrUsed === null ? t("inputs.crrAuto") : fmt.number(crrUsed, 4, 4);
    const value = conditions[key];
    return value == null ? "" : fmt.number(value, 1);
  };
  const hint = (key: InputKey): string | undefined => {
    if (key === "rider_kg" && draft.rider_kg.trim() === "" && conditions?.rider_kg_date) {
      return t("inputs.weightFrom", { date: fmt.date(conditions.rider_kg_date) });
    }
    if (key === "crr" && draft.crr.trim() === "") return t("inputs.crrAuto");
    return undefined;
  };

  const weighed = weighedBikes(bikes);
  const typedBikeKg = readInputs(draft).inputs.bike_kg;
  const bike = bikeOfWeight(weighed, typedBikeKg);

  return (
    <div className="aero-lab__inputs">
      <BikeSelect
        bikes={weighed}
        value={bike?.id ?? null}
        onChange={(picked) => onChange("bike_kg", picked?.weight_kg != null ? String(picked.weight_kg) : "")}
        emptyLabel={typedBikeKg == null ? t("inputs.sessionBike") : t("inputs.typedBike")}
      />
      {INPUT_KEYS.map((key) => (
        <Input
          key={key}
          label={t(`inputs.${key}`)}
          suffix={SUFFIX[key]}
          inputMode="decimal"
          autoComplete="off"
          value={draft[key]}
          placeholder={placeholder(key)}
          hint={hint(key)}
          error={
            invalid.includes(key)
              ? t("inputs.range", { min: fmt.number(INPUT_BOUNDS[key].min, 4), max: fmt.number(INPUT_BOUNDS[key].max, 4) })
              : undefined
          }
          onChange={(event) => onChange(key, event.target.value)}
        />
      ))}
      {conditions && <p className="ui-card__hint aero-lab__rho">{t("inputs.rho", { value: fmt.number(conditions.rho, 3, 3) })}</p>}
    </div>
  );
}
