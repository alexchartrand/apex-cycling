import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Card, DataTable, Input, Select, StatTile, type DataTableColumn } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { gearChoices, gearOf } from "../equipment/gear";
import { parseTimeInput } from "../records/timeInput";
import { cadenceForLapTime, cadenceTable, type CadenceRow } from "./gearing";
import { developmentM, gearInches } from "./physics";
import { NO_GEAR } from "./toolInputs";
import { NumberField, TrackSelect } from "./ToolFields";
import type { ToolInputs } from "./useToolInputs";

export function GearingTool({ inputs }: { inputs: ToolInputs }) {
  const { t } = useTranslation("tools");
  const { t: tc } = useTranslation("common");
  const fmt = useFormat();
  const [targetLap, setTargetLap] = useState("");
  const chainring = inputs.field("chainring").value;
  const cog = inputs.field("cog").value;
  const rollout = inputs.field("rolloutM").value;
  const lap = inputs.field("lapM").value;
  const gearValid = chainring !== null && cog !== null && rollout !== null;
  const targetLapMs = parseTimeInput(targetLap);
  const choices = gearChoices(inputs.bikes);
  // "none" once chosen, even if the typical gear happens to be a saved one.
  const savedGear = inputs.noGear ? null : gearOf(inputs.bikes, chainring, cog, rollout === null ? null : rollout * 1000);
  const pickGear = (gearId: string) => {
    if (gearId === NO_GEAR) {
      inputs.setGear(null);
      return;
    }
    const gear = inputs.bikes.flatMap((bike) => bike.gears).find((candidate) => candidate.id === gearId);
    if (gear) inputs.setGear({ chainring: gear.chainring_teeth, cog: gear.cog_teeth, rolloutM: gear.rollout_mm / 1000 });
  };

  const columns: DataTableColumn<CadenceRow>[] = [
    { id: "cadence", header: t("gearing.cadence"), cell: (row) => `${row.cadenceRpm} ${tc("units.rpm")}`, primary: true },
    { id: "speed", header: t("gearing.speed"), align: "right", cell: (row) => `${fmt.number(row.speedKmh, 1, 1)} ${tc("units.kmh")}` },
    { id: "lap", header: t("gearing.lapTime"), align: "right", cell: (row) => fmt.seconds(row.lapS * 1000, 2) },
    { id: "f200", header: t("gearing.flying200"), align: "right", cell: (row) => fmt.seconds(row.flying200S * 1000, 2) },
  ];

  return (
    <div className="tools-tool">
      <Card title={t("gearing.title")} as="section">
        <div className="tools-grid">
          {choices.length > 0 && (
            <Select
              label={t("gearing.savedGear")}
              value={savedGear?.id ?? (inputs.noGear ? NO_GEAR : "")}
              onChange={(event) => pickGear(event.target.value)}
            >
              {!inputs.noGear && savedGear == null && (
                <option value="" disabled>
                  {t("gearing.typedGear")}
                </option>
              )}
              <option value={NO_GEAR}>{t("gearing.noGear")}</option>
              {choices.map((choice) => (
                <option key={choice.id} value={choice.id}>
                  {choice.label}
                </option>
              ))}
            </Select>
          )}
          <NumberField inputs={inputs} name="chainring" label={t("gearing.chainring")} />
          <NumberField inputs={inputs} name="cog" label={t("gearing.cog")} />
          <NumberField inputs={inputs} name="rolloutM" label={t("gearing.rollout")} suffix="m" hint={t("gearing.rolloutHint")} />
          <TrackSelect inputs={inputs} />
          <NumberField inputs={inputs} name="lapM" label={t("effort.lap")} suffix="m" />
        </div>
      </Card>

      {!gearValid ? (
        <p className="tools-note">{t("results.invalid")}</p>
      ) : (
        <>
          <div className="tools-results">
            <StatTile label={t("gearing.ratio")} value={`${chainring}×${cog}`} hint={fmt.number(chainring / cog, 3, 3)} />
            <StatTile
              label={t("gearing.development")}
              value={fmt.number(developmentM(chainring, cog, rollout), 2, 2)}
              unit="m"
              tone="accent"
              size="lg"
            />
            <StatTile label={t("gearing.gearInches")} value={fmt.number(gearInches(chainring, cog, rollout), 1, 1)} unit="in" />
          </div>
          {lap !== null && (
            <Card title={t("gearing.tableTitle")} as="section" padding="flush">
              <div className="tools-inline-form">
                <Input
                  label={t("gearing.targetLap")}
                  hint={t("effort.timeHint")}
                  inputMode="decimal"
                  autoComplete="off"
                  value={targetLap}
                  onChange={(event) => setTargetLap(event.target.value)}
                  suffix={tc("units.s")}
                />
                {targetLapMs !== null && (
                  <StatTile
                    label={t("gearing.cadenceNeeded")}
                    value={fmt.number(cadenceForLapTime(targetLapMs / 1000, lap, chainring, cog, rollout), 0)}
                    unit={tc("units.rpm")}
                  />
                )}
              </div>
              <DataTable
                columns={columns}
                rows={cadenceTable(chainring, cog, rollout, lap)}
                getRowId={(row) => String(row.cadenceRpm)}
                caption={t("gearing.caption")}
                layout="table"
                dense
              />
            </Card>
          )}
        </>
      )}
    </div>
  );
}
