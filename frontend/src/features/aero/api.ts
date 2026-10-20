import { apiFetch } from "../../api/client";
import type { AeroEstimate, AeroEstimateRequest, AeroTest, AeroTestCreate, AeroTestDetail, AeroTestUpdate } from "./types";

const base = (athleteId: string) => `/athletes/${athleteId}`;

/** Computes only: nothing is saved. */
export function estimateAero(athleteId: string, eventId: string, request: AeroEstimateRequest): Promise<AeroEstimate> {
  return apiFetch<AeroEstimate>(`${base(athleteId)}/sessions/${encodeURIComponent(eventId)}/aero`, {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function listAeroTests(athleteId: string): Promise<AeroTest[]> {
  return apiFetch<AeroTest[]>(`${base(athleteId)}/aero-tests`);
}

export function createAeroTest(athleteId: string, payload: AeroTestCreate): Promise<AeroTestDetail> {
  return apiFetch<AeroTestDetail>(`${base(athleteId)}/aero-tests`, { method: "POST", body: JSON.stringify(payload) });
}

export function updateAeroTest(athleteId: string, testId: string, payload: AeroTestUpdate): Promise<AeroTestDetail> {
  return apiFetch<AeroTestDetail>(`${base(athleteId)}/aero-tests/${testId}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function deleteAeroTest(athleteId: string, testId: string): Promise<void> {
  return apiFetch<void>(`${base(athleteId)}/aero-tests/${testId}`, { method: "DELETE" });
}
