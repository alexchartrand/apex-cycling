import { useQuery } from "@tanstack/react-query";
import { listRecords } from "./api";

/** The athlete's records board (best per place, event and start type). */
export function useRecords(athleteId: string) {
  return useQuery({
    queryKey: ["records", athleteId],
    queryFn: () => listRecords(athleteId),
    enabled: athleteId !== "",
  });
}
