import { apiFetch } from "../../api/client";
import type { AdminOverview } from "./types";

export function fetchAdminOverview(): Promise<AdminOverview> {
  return apiFetch<AdminOverview>("/admin/overview");
}
