import { apiFetch } from "../../api/client";
import type { Bike, BikePayload, Gear, GearPayload } from "./types";

const base = (athleteId: string) => `/athletes/${athleteId}`;

export function listBikes(athleteId: string): Promise<Bike[]> {
  return apiFetch<Bike[]>(`${base(athleteId)}/bikes`);
}

export function createBike(athleteId: string, payload: BikePayload): Promise<Bike> {
  return apiFetch<Bike>(`${base(athleteId)}/bikes`, { method: "POST", body: JSON.stringify(payload) });
}

export function updateBike(athleteId: string, bikeId: string, payload: BikePayload): Promise<Bike> {
  return apiFetch<Bike>(`${base(athleteId)}/bikes/${bikeId}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function deleteBike(athleteId: string, bikeId: string): Promise<void> {
  return apiFetch<void>(`${base(athleteId)}/bikes/${bikeId}`, { method: "DELETE" });
}

export function createGear(athleteId: string, bikeId: string, payload: Required<Omit<GearPayload, "tire" | "crr">> & { tire?: string | null; crr?: number | null }): Promise<Gear> {
  return apiFetch<Gear>(`${base(athleteId)}/bikes/${bikeId}/gears`, { method: "POST", body: JSON.stringify(payload) });
}

export function updateGear(athleteId: string, gearId: string, payload: GearPayload): Promise<Gear> {
  return apiFetch<Gear>(`${base(athleteId)}/gears/${gearId}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function deleteGear(athleteId: string, gearId: string): Promise<void> {
  return apiFetch<void>(`${base(athleteId)}/gears/${gearId}`, { method: "DELETE" });
}

export function setSessionGear(athleteId: string, eventId: string, gearId: string | null): Promise<void> {
  return apiFetch<void>(`${base(athleteId)}/sessions/${encodeURIComponent(eventId)}/gear`, {
    method: "PUT",
    body: JSON.stringify({ gear_setup_id: gearId }),
  });
}

export function setEffortGear(athleteId: string, eventId: string, firstLapId: string, gearId: string | null): Promise<void> {
  return apiFetch<void>(`${base(athleteId)}/sessions/${encodeURIComponent(eventId)}/efforts/${firstLapId}/gear`, {
    method: "PUT",
    body: JSON.stringify({ gear_setup_id: gearId }),
  });
}
