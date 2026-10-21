import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createBike, createGear, deleteBike, deleteGear, listBikes, setEffortGear, setSessionGear, updateBike, updateGear } from "./api";
import type { BikePayload, GearPayload } from "./types";

export function useBikes(athleteId: string) {
  return useQuery({ queryKey: ["bikes", athleteId], queryFn: () => listBikes(athleteId), enabled: athleteId !== "" });
}

/** Gears feed the session views (estimated cadence) and the aero default bike weight, so those refetch too. */
function useInvalidateEquipment(athleteId: string) {
  const queryClient = useQueryClient();
  return () =>
    Promise.all(
      ["bikes", "session-detail", "session-efforts", "aero-estimate", "aero-tests"].map((key) =>
        queryClient.invalidateQueries({ queryKey: [key, athleteId] }),
      ),
    );
}

export function useSaveBike(athleteId: string) {
  const invalidate = useInvalidateEquipment(athleteId);
  return useMutation({
    mutationFn: ({ bikeId, payload }: { bikeId?: string; payload: BikePayload }) =>
      bikeId ? updateBike(athleteId, bikeId, payload) : createBike(athleteId, payload),
    onSuccess: invalidate,
  });
}

export function useDeleteBike(athleteId: string) {
  const invalidate = useInvalidateEquipment(athleteId);
  return useMutation({ mutationFn: (bikeId: string) => deleteBike(athleteId, bikeId), onSuccess: invalidate });
}

export function useSaveGear(athleteId: string) {
  const invalidate = useInvalidateEquipment(athleteId);
  return useMutation({
    mutationFn: (args: { bikeId: string; gearId?: string; payload: Required<Omit<GearPayload, "tire" | "crr">> & { tire: string | null; crr: number | null } }) =>
      args.gearId ? updateGear(athleteId, args.gearId, args.payload) : createGear(athleteId, args.bikeId, args.payload),
    onSuccess: invalidate,
  });
}

export function useDeleteGear(athleteId: string) {
  const invalidate = useInvalidateEquipment(athleteId);
  return useMutation({ mutationFn: (gearId: string) => deleteGear(athleteId, gearId), onSuccess: invalidate });
}

export function useSessionGear(athleteId: string, eventId: string) {
  const invalidate = useInvalidateEquipment(athleteId);
  return useMutation({ mutationFn: (gearId: string | null) => setSessionGear(athleteId, eventId, gearId), onSuccess: invalidate });
}

export function useEffortGear(athleteId: string, eventId: string) {
  const invalidate = useInvalidateEquipment(athleteId);
  return useMutation({
    mutationFn: ({ firstLapId, gearId }: { firstLapId: string; gearId: string | null }) =>
      setEffortGear(athleteId, eventId, firstLapId, gearId),
    onSuccess: invalidate,
  });
}
