import { useDeferredValue, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Card, DataTable, Input, SegmentedControl, StatTile, type DataTableColumn } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { airDensity, powerForTimeW, simulate, type Ride } from "./physics";
import { ConditionsCard, NumberField, RiderCard, StartControl } from "./ToolFields";
import { MODE_PARAM, TIME_PARAM } from "./toolInputs";
import type { ToolInputs } from "./useToolInputs";
import { sensitivities, TEMP_STEP_C, type Sensitivity } from "./whatIf";

type Mode = "time" | "power";

type Result =
  | { kind: "invalid" }
  | { kind: "unreachable" }
  | { kind: "ok"; racePower: number; ride: Ride; rows: Sensitivity[] };

export function PowerTool({ inputs }: { inputs: ToolInputs }) {
  const { t } = useTranslation("tools");
  const { t: tc } = useTranslation("common");
  const fmt = useFormat();
  const mode: Mode = inputs.params.get(MODE_PARAM) === "power" ? "power" : "time";
  const standing = inputs.start === "standing";
  const distance = inputs.field("distanceM").value;
  const power = inputs.field("powerW").value;
  const targetS = inputs.time.seconds;
  const riderKg = inputs.field("riderKg").value;

  // Air 5 °C warmer, the other air inputs unchanged.
  const temp = inputs.field("tempC").value;
  const pressure = inputs.field("pressureHpa").value;
  const elevation = inputs.field("elevationM").value;
  const humidity = inputs.field("humidityPct").value;
  const warmerRho =
    temp === null || elevation === null || humidity === null
      ? null
      : airDensity(temp + TEMP_STEP_C, {
          pressurePa: pressure === null ? null : pressure * 100,
          elevationM: elevation,
          humidityPct: humidity,
        });

  // The solver runs ~100 simulations; deferring keeps typing responsive.
  const deferred = useDeferredValue({ setup: inputs.setup, distance, power, targetS, mode, standing, warmerRho });
  const result = useMemo((): Result => {
    const { setup, distance: d, power: p, targetS: target, mode: m, standing: s, warmerRho: warm } = deferred;
    const given = m === "time" ? p : target;
    if (setup === null || d === null || given === null) return { kind: "invalid" };
    const racePower = m === "time" ? given : powerForTimeW(d, given, setup, { standing: s });
    const ride = racePower === null ? null : simulate(d, racePower, setup, { standing: s });
    if (racePower === null || ride === null) return { kind: "unreachable" };
    const rows = warm === null ? [] : sensitivities({ setup, distanceM: d, powerW: racePower, standing: s }, warm);
    return { kind: "ok", racePower, ride, rows };
  }, [deferred]);

  const columns: DataTableColumn<Sensitivity>[] = [
    { id: "change", header: t("sensitivity.change"), cell: (row) => t(`sensitivity.rows.${row.key}`), primary: true },
    {
      id: "time",
      header: t("sensitivity.time"),
      align: "right",
      cell: (row) => (row.deltaTimeS === null ? "—" : `${fmt.deltaSeconds(row.deltaTimeS * 1000, 2)} ${tc("units.s")}`),
    },
    {
      id: "power",
      header: t("sensitivity.power"),
      align: "right",
      cell: (row) =>
        row.deltaPowerW === null ? "—" : t("sensitivity.watts", { value: signed(fmt.number(row.deltaPowerW, 0), row.deltaPowerW) }),
    },
  ];

  return (
    <div className="tools-tool">
      <Card title={t("effort.title")} as="section">
        <div className="tools-grid">
          <NumberField inputs={inputs} name="distanceM" label={t("effort.distance")} suffix="m" />
          <StartControl inputs={inputs} />
          <div className="field">
            <span className="field__label">{t("effort.mode")}</span>
            <SegmentedControl<Mode>
              aria-label={t("effort.mode")}
              value={mode}
              onChange={(value) => inputs.setParam(MODE_PARAM, value)}
              options={[
                { value: "time", label: t("effort.timeForPower") },
                { value: "power", label: t("effort.powerForTime") },
              ]}
            />
          </div>
          {mode === "time" ? (
            <NumberField inputs={inputs} name="powerW" label={t("effort.power")} suffix={tc("units.w")} hint={t("effort.powerHint")} />
          ) : (
            <Input
              label={t("effort.time")}
              hint={t("effort.timeHint")}
              error={inputs.time.invalid ? t("errors.time") : undefined}
              inputMode="decimal"
              autoComplete="off"
              value={inputs.time.raw}
              onChange={(event) => inputs.setParam(TIME_PARAM, event.target.value)}
            />
          )}
        </div>
      </Card>

      {result.kind === "invalid" ? (
        <p className="tools-note">{t("results.invalid")}</p>
      ) : result.kind === "unreachable" ? (
        <p className="tools-note" role="status">
          {t("results.unreachable")}
        </p>
      ) : (
        <>
          <div className="tools-results">
            <StatTile label={t("results.time")} value={fmt.lapTime(result.ride.timeS * 1000)} tone="accent" size="lg" />
            <StatTile
              label={t("results.speed")}
              value={fmt.speedKmh(deferred.distance ?? 0, result.ride.timeS * 1000)}
              unit={tc("units.kmh")}
            />
            <StatTile
              label={t("results.racePower")}
              value={fmt.number(result.racePower, 0)}
              unit={tc("units.w")}
              hint={riderKg ? `${fmt.number(result.racePower / riderKg, 2, 2)} ${tc("units.wkg")}` : undefined}
            />
            {standing && (
              <StatTile
                label={t("results.averagePower")}
                value={fmt.number(result.ride.averagePowerW, 0)}
                unit={tc("units.w")}
                hint={t("results.averageHint")}
              />
            )}
          </div>
          {result.rows.length > 0 && (
            <Card title={t("sensitivity.title")} as="section" padding="flush">
              <p className="tools-card-description">
                {t("sensitivity.description", { distance: fmt.distance(deferred.distance) })}
              </p>
              <DataTable columns={columns} rows={result.rows} getRowId={(row) => row.key} caption={t("sensitivity.title")} dense />
            </Card>
          )}
        </>
      )}

      <RiderCard inputs={inputs} />
      <ConditionsCard inputs={inputs} />
    </div>
  );
}

function signed(text: string, value: number): string {
  return value > 0 ? `+${text}` : value < 0 ? text.replace("-", "−") : text;
}
