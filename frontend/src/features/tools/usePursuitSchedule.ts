import { useDeferredValue, useMemo } from "react";
import { pursuitSchedule } from "./pursuitSchedule";
import type { NumberKey } from "./toolInputs";
import { AIR_KEYS, SETUP_KEYS, type ToolInputs } from "./useToolInputs";

/** Everything the schedule depends on, for the board link. */
export const PURSUIT_KEYS: NumberKey[] = ["distanceM", "lapM", ...SETUP_KEYS, ...AIR_KEYS];

export function usePursuitSchedule(inputs: ToolInputs) {
  const distance = inputs.field("distanceM").value;
  const lap = inputs.field("lapM").value;
  const deferred = useDeferredValue({ setup: inputs.setup, distance, lap, target: inputs.time.seconds });
  return useMemo(() => {
    const { setup, distance: d, lap: l, target } = deferred;
    if (setup === null || d === null || l === null || target === null) return { kind: "invalid" } as const;
    const schedule = pursuitSchedule(d, target, l, setup);
    return schedule === null ? ({ kind: "unreachable" } as const) : ({ kind: "ok", schedule } as const);
  }, [deferred]);
}
