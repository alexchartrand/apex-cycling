import { apiFetch } from "../../api/client";
import type { Athlete } from "./types";

export function fetchMyAthlete(): Promise<Athlete> {
  return apiFetch<Athlete>("/athletes/me");
}
