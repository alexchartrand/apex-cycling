/*
  Cycling physics: air density, the power equation and its solvers.

  A one-for-one mirror of backend/app/analysis/physics.py (same algorithms and
  constants, names in camelCase); physics.test.ts checks it against
  shared/physics-test-vectors.json, which the Python side generates. Change the
  two together. See the Python module for the model's assumptions.

    P = (v·(½ρ·CdA·v² + Crr·m·g) + m_eff·a·v) / η
*/

export const G = 9.80665;
const R_DRY_AIR = 287.058;
const R_WATER_VAPOR = 461.495;
export const SEA_LEVEL_PRESSURE_PA = 101_325;
const ZERO_CELSIUS_K = 273.15;

export const DEFAULT_CRR = 0.0025;
export const DEFAULT_EFFICIENCY = 0.98;
export const DEFAULT_ROTATING_MASS_KG = 1.2;
/** Standing starts ride at this × race power until reaching race pace. */
export const DEFAULT_START_POWER_RATIO = 2.0;
/** Cap on the propulsive force at the wheel (torque-limited first strokes). */
export const DEFAULT_START_FORCE_N = 300.0;

export const SIMULATION_STEP_S = 0.02;
const MAX_SIMULATION_S = 3600;

/** A rider on a bike: mass is rider + bike + kit, rho the air density. */
export type Setup = {
  massKg: number;
  cdaM2: number;
  rho: number;
  crr: number;
  efficiency: number;
  rotatingMassKg: number;
};

export type Ride = {
  timeS: number;
  finalSpeedMs: number;
  /** Includes the start, so above race power after a standing start. */
  averagePowerW: number;
  /** Elapsed time at each multiple of splitEveryM strictly inside the distance. */
  splitTimesS: number[];
};

export type EffortOptions = {
  standing?: boolean;
  splitEveryM?: number | null;
  startPowerRatio?: number;
  startForceN?: number;
};

export function makeSetup(
  values: Pick<Setup, "massKg" | "cdaM2" | "rho"> & Partial<Setup>,
): Setup {
  return {
    crr: DEFAULT_CRR,
    efficiency: DEFAULT_EFFICIENCY,
    rotatingMassKg: DEFAULT_ROTATING_MASS_KG,
    ...values,
  };
}

// --- Air ---------------------------------------------------------------------

/** Tetens' formula, good to ~0.1% between 0 and 50 °C. */
export function saturationVaporPressurePa(tempC: number): number {
  return 610.78 * 10 ** ((7.5 * tempC) / (tempC + 237.3));
}

/** Standard-atmosphere station pressure, for when there's no barometer reading. */
export function pressureAtElevationPa(elevationM: number): number {
  const base = 1 - 2.25577e-5 * elevationM;
  if (base <= 0) {
    // Beyond ~44.3 km the base goes negative and the fractional power is NaN.
    throw new Error(`elevationM is beyond the barometric formula's domain: ${elevationM}`);
  }
  return SEA_LEVEL_PRESSURE_PA * base ** 5.25588;
}

/**
 * Density of moist air in kg/m³. `pressurePa` is the actual station pressure;
 * without it the pressure is estimated from `elevationM`.
 */
export function airDensity(
  tempC: number,
  {
    pressurePa = null,
    elevationM = 0,
    humidityPct = 0,
  }: { pressurePa?: number | null; elevationM?: number; humidityPct?: number } = {},
): number {
  const tempK = tempC + ZERO_CELSIUS_K;
  if (tempK <= 0) throw new Error(`tempC must be above absolute zero: ${tempC}`);
  if (humidityPct < 0 || humidityPct > 100) {
    throw new Error(`humidityPct must be within 0..100: ${humidityPct}`);
  }
  const pressure = pressurePa ?? pressureAtElevationPa(elevationM);
  const vapor = (humidityPct / 100) * saturationVaporPressurePa(tempC);
  return (pressure - vapor) / (R_DRY_AIR * tempK) + vapor / (R_WATER_VAPOR * tempK);
}

// --- Power equation ----------------------------------------------------------

/** The model needs a real rider in real air; anything else is a caller bug
 * (a zeroed field, a negative CdA from a bad aero fit) and would otherwise
 * surface as NaN deep inside a solve. */
function checkSetup(setup: Setup): void {
  if (setup.massKg <= 0) throw new Error(`massKg must be positive: ${setup.massKg}`);
  if (setup.cdaM2 <= 0) throw new Error(`cdaM2 must be positive: ${setup.cdaM2}`);
  if (setup.rho <= 0) throw new Error(`rho must be positive: ${setup.rho}`);
  if (setup.efficiency <= 0) throw new Error(`efficiency must be positive: ${setup.efficiency}`);
  if (setup.crr < 0) throw new Error(`crr must not be negative: ${setup.crr}`);
  if (setup.rotatingMassKg < 0) {
    throw new Error(`rotatingMassKg must not be negative: ${setup.rotatingMassKg}`);
  }
}

/** Aerodynamic drag + rolling resistance at a speed. */
export function resistiveForceN(speedMs: number, setup: Setup): number {
  return 0.5 * setup.rho * setup.cdaM2 * speedMs ** 2 + setup.crr * setup.massKg * G;
}

/** Pedal power to hold (or, with accelMs2, change) a speed. */
export function powerRequiredW(speedMs: number, setup: Setup, accelMs2 = 0): number {
  checkSetup(setup);
  const effectiveMass = setup.massKg + setup.rotatingMassKg;
  const wheelPower = speedMs * resistiveForceN(speedMs, setup) + effectiveMass * accelMs2 * speedMs;
  return wheelPower / setup.efficiency;
}

/** The speed a constant power holds (Cardano on ½ρCdA·v³ + Crr·m·g·v = η·P). */
export function steadySpeedMs(powerW: number, setup: Setup): number {
  checkSetup(setup);
  if (powerW <= 0) return 0;
  const a = 0.5 * setup.rho * setup.cdaM2;
  const p = (setup.crr * setup.massKg * G) / a;
  const q = (-setup.efficiency * powerW) / a;
  const root = Math.sqrt((q * q) / 4 + p ** 3 / 27);
  return Math.cbrt(-q / 2 + root) + Math.cbrt(-q / 2 - root);
}

// --- Efforts -----------------------------------------------------------------

function riderPowerW(speedMs: number, powerW: number, raceSpeedMs: number, startPowerRatio: number) {
  return speedMs < raceSpeedMs ? powerW * startPowerRatio : powerW;
}

function acceleration(speedMs: number, riderPower: number, setup: Setup, startForceN: number) {
  const drivePower = setup.efficiency * riderPower;
  // min(F_max, ηP/v), written so v = 0 never divides. No drive power means
  // no drive force: the cap must not push a rider who isn't pedalling.
  let driveForce: number;
  if (drivePower <= 0) {
    driveForce = 0;
  } else if (speedMs <= 0 || speedMs * startForceN <= drivePower) {
    driveForce = startForceN;
  } else {
    driveForce = drivePower / speedMs;
  }
  if (speedMs <= 0 && driveForce <= resistiveForceN(0, setup)) return 0;
  return (driveForce - resistiveForceN(speedMs, setup)) / (setup.massKg + setup.rotatingMassKg);
}

/**
 * Ride `distanceM` at race power `powerW`, standing (from v = 0 at
 * startPowerRatio × race power, force-capped, until race pace) or flying.
 * Fixed-step RK4; null if the rider can't finish within an hour or has no
 * power to ride with.
 */
export function simulate(
  distanceM: number,
  powerW: number,
  setup: Setup,
  {
    standing = true,
    splitEveryM = null,
    startPowerRatio = DEFAULT_START_POWER_RATIO,
    startForceN = DEFAULT_START_FORCE_N,
  }: EffortOptions = {},
): Ride | null {
  const raceSpeed = steadySpeedMs(powerW, setup);
  if (distanceM <= 0) {
    return { timeS: 0, finalSpeedMs: standing ? 0 : raceSpeed, averagePowerW: 0, splitTimesS: [] };
  }
  if (powerW <= 0) {
    return null; // no power, no ride: the force cap must not carry a stopped rider
  }
  const dt = SIMULATION_STEP_S;
  const marks: number[] = [];
  if (splitEveryM && splitEveryM > 0) {
    const count = Math.ceil(distanceM / splitEveryM) - 1;
    for (let i = 0; i < count; i++) marks.push(splitEveryM * (i + 1));
  }
  const splits: number[] = [];
  const accel = (v: number) =>
    acceleration(v, riderPowerW(v, powerW, raceSpeed, startPowerRatio), setup, startForceN);

  let t = 0;
  let x = 0;
  let energy = 0;
  let v = standing ? 0 : raceSpeed;
  while (t < MAX_SIMULATION_S) {
    const k1v = accel(v);
    const k1x = v;
    const k2v = accel(v + (dt / 2) * k1v);
    const k2x = v + (dt / 2) * k1v;
    const k3v = accel(v + (dt / 2) * k2v);
    const k3x = v + (dt / 2) * k2v;
    const k4v = accel(v + dt * k3v);
    const k4x = v + dt * k3v;
    const nextX = x + (dt / 6) * (k1x + 2 * k2x + 2 * k3x + k4x);
    const nextV = Math.max(0, v + (dt / 6) * (k1v + 2 * k2v + 2 * k3v + k4v));
    const stepPower = riderPowerW(v, powerW, raceSpeed, startPowerRatio);
    while (splits.length < marks.length && nextX >= marks[splits.length]) {
      const mark = marks[splits.length];
      splits.push(t + (dt * (mark - x)) / (nextX - x));
    }
    if (nextX >= distanceM) {
      const fraction = (distanceM - x) / (nextX - x);
      const time = t + dt * fraction;
      energy += stepPower * dt * fraction;
      return {
        timeS: time,
        finalSpeedMs: v + (nextV - v) * fraction,
        averagePowerW: energy / time,
        splitTimesS: splits,
      };
    }
    t += dt;
    x = nextX;
    v = nextV;
    energy += stepPower * dt;
  }
  return null;
}

/** The race power that rides distanceM in timeS (bisection, to 0.01 W); null if 3000 W can't. */
export function powerForTimeW(
  distanceM: number,
  timeS: number,
  setup: Setup,
  options: Omit<EffortOptions, "splitEveryM"> = {},
): number | null {
  let low = 0;
  let high = 3000;
  const finish = (power: number) =>
    simulate(distanceM, power, setup, { ...options, splitEveryM: null })?.timeS ?? Infinity;
  if (timeS <= 0 || finish(high) > timeS) return null;
  while (high - low > 0.01) {
    const mid = (low + high) / 2;
    if (finish(mid) > timeS) low = mid;
    else high = mid;
  }
  return high;
}

// --- Gearing -----------------------------------------------------------------

/** Distance covered per crank revolution. */
export function developmentM(chainring: number, cog: number, rolloutM: number): number {
  return (chainring / cog) * rolloutM;
}

export const GEAR_INCHES_WHEEL_IN = 27;

/** Ratio × a nominal 27-inch wheel, whatever the real tire, as gear tables do. */
export function gearInches(chainring: number, cog: number): number {
  return (chainring / cog) * GEAR_INCHES_WHEEL_IN;
}

export function speedFromCadenceMs(cadenceRpm: number, chainring: number, cog: number, rolloutM: number) {
  return (cadenceRpm / 60) * developmentM(chainring, cog, rolloutM);
}

export function cadenceFromSpeedRpm(speedMs: number, chainring: number, cog: number, rolloutM: number) {
  return (speedMs / developmentM(chainring, cog, rolloutM)) * 60;
}
