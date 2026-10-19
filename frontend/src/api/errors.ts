import i18n from "../i18n";
import { ApiError } from "./client";

/**
 * A user-facing message for a failed request. `byStatus` maps HTTP statuses
 * to already-translated messages for the cases a screen knows about (e.g.
 * 401 on login = wrong password). Otherwise the backend's `detail` is shown
 * (English-only for now, but specific), falling back to a generic message.
 */
export function errorMessage(error: unknown, byStatus: Partial<Record<number, string>> = {}): string {
  if (error instanceof ApiError) {
    const mapped = byStatus[error.status];
    if (mapped) return mapped;
    if (error.message) return error.message;
    return i18n.t("unknownError", { ns: "common" });
  }
  // fetch() rejects with a TypeError when the server is unreachable.
  if (error instanceof TypeError) return i18n.t("networkError", { ns: "common" });
  return i18n.t("unknownError", { ns: "common" });
}
