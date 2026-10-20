import { useTranslation } from "react-i18next";
import { StatTile } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { airDensity, pressureAtElevationPa } from "./physics";
import { ConditionsCard } from "./ToolFields";
import type { ToolInputs } from "./useToolInputs";

const STANDARD_RHO = airDensity(15);

export function AirDensityTool({ inputs }: { inputs: ToolInputs }) {
  const { t } = useTranslation("tools");
  const fmt = useFormat();
  const pressure = inputs.field("pressureHpa");
  const elevation = inputs.field("elevationM");
  const pressureHpa = pressure.value ?? (elevation.value === null ? null : pressureAtElevationPa(elevation.value) / 100);
  const dragChangePct = inputs.rho === null ? null : (inputs.rho / STANDARD_RHO - 1) * 100;

  return (
    <div className="tools-tool">
      <ConditionsCard inputs={inputs} />
      {inputs.rho === null ? (
        <p className="tools-note">{t("results.invalid")}</p>
      ) : (
        <div className="tools-results">
          <StatTile label={t("air.rho")} value={fmt.number(inputs.rho, 4, 4)} unit="kg/m³" tone="accent" size="lg" />
          <StatTile
            label={t("airTool.pressureUsed")}
            value={fmt.number(pressureHpa, 1, 1)}
            unit="hPa"
            hint={pressure.value === null ? t("airTool.estimated") : t("airTool.measured")}
          />
          {dragChangePct !== null && (
            <StatTile
              label={t("airTool.vsStandard")}
              value={
                dragChangePct <= 0
                  ? t("airTool.lessDrag", { value: fmt.number(-dragChangePct, 1, 1) })
                  : t("airTool.moreDrag", { value: fmt.number(dragChangePct, 1, 1) })
              }
              hint={t("airTool.standardHint")}
            />
          )}
        </div>
      )}
    </div>
  );
}
