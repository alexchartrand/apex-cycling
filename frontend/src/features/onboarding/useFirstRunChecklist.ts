import { useState } from "react";
import { useActiveAthlete } from "../athletes/useActiveAthlete";
import { useCurrentMetrics } from "../athletes/useAthlete";
import { useViewingAthleteId } from "../athletes/viewing";
import { useTransponderAssignments } from "../connections/useConnections";
import { useMyCoaches } from "../coaching/useCoaching";
import { buildChecklist, dismiss, isDismissed } from "./checklist";

/**
 * The first-run checklist for the signed-in user's own athlete. Never shown
 * while viewing someone else's data, once finished, or after it was hidden.
 */
export function useFirstRunChecklist() {
  const athlete = useActiveAthlete().data;
  const viewingOther = useViewingAthleteId() !== null;
  const athleteId = athlete?.id ?? "";
  const assignments = useTransponderAssignments(athleteId);
  const metrics = useCurrentMetrics(athleteId);
  const coaches = useMyCoaches();
  const [hiddenNow, setHiddenNow] = useState(false);

  const loaded = athlete != null && assignments.data !== undefined && metrics.data !== undefined && coaches.data !== undefined;
  const checklist = loaded
    ? buildChecklist({
        transponders: assignments.data!.length,
        weightKg: metrics.data!.weight_kg?.value ?? null,
        clubs: athlete.club_ids.length,
        activeCoaches: coaches.data!.filter((link) => link.status === "active").length,
      })
    : null;

  const visible = checklist !== null && !checklist.complete && !viewingOther && !hiddenNow && !isDismissed(athleteId);

  return {
    visible,
    checklist,
    hide() {
      dismiss(athleteId);
      setHiddenNow(true);
    },
  };
}
