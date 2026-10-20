import { powerForTimeW, simulate, type Setup } from "./physics";

/** One "what if I changed X" row: X's effect at the same race power. */
export type SensitivityKey = "cdaDown" | "cdaUp" | "massDown" | "powerUp" | "crrDown" | "warmer";

export type Sensitivity = {
  key: SensitivityKey;
  /** Finish time change at the same race power (negative = faster). */
  deltaTimeS: number | null;
  /** Race power change for the same finish time (negative = saves watts). */
  deltaPowerW: number | null;
};

export type Scenario = { setup: Setup; distanceM: number; powerW: number; standing: boolean };

export const CDA_STEP = 0.01;
export const MASS_STEP_KG = 1;
export const POWER_STEP_W = 10;
export const CRR_STEP = 0.0005;
export const TEMP_STEP_C = 5;

export function finishTimeS({ setup, distanceM, powerW, standing }: Scenario): number | null {
  return simulate(distanceM, powerW, setup, { standing })?.timeS ?? null;
}

/**
 * The sensitivity table: each change applied alone to the scenario.
 * `warmerRho` is the air density 5 °C warmer (the caller owns the air inputs).
 */
export function sensitivities(base: Scenario, warmerRho: number): Sensitivity[] {
  const baseTime = finishTimeS(base);
  const { setup } = base;
  const changes: [SensitivityKey, Scenario][] = [
    ["cdaDown", { ...base, setup: { ...setup, cdaM2: setup.cdaM2 - CDA_STEP } }],
    ["cdaUp", { ...base, setup: { ...setup, cdaM2: setup.cdaM2 + CDA_STEP } }],
    ["massDown", { ...base, setup: { ...setup, massKg: setup.massKg - MASS_STEP_KG } }],
    ["powerUp", { ...base, powerW: base.powerW + POWER_STEP_W }],
    ["crrDown", { ...base, setup: { ...setup, crr: Math.max(0, setup.crr - CRR_STEP) } }],
    ["warmer", { ...base, setup: { ...setup, rho: warmerRho } }],
  ];
  return changes.map(([key, scenario]) => {
    const time = finishTimeS(scenario);
    let deltaPowerW: number | null;
    if (key === "powerUp") {
      deltaPowerW = POWER_STEP_W;
    } else {
      const power = baseTime === null ? null : powerForTimeW(scenario.distanceM, baseTime, scenario.setup, { standing: scenario.standing });
      deltaPowerW = power === null ? null : power - base.powerW;
    }
    return { key, deltaTimeS: time === null || baseTime === null ? null : time - baseTime, deltaPowerW };
  });
}
