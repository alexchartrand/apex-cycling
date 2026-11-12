import { ApiError } from "../../api/client";
import { errorMessage } from "../../api/errors";

type Key = "errors.cap" | "errors.failed" | "errors.unavailable";

/** A failed AI coach request in the athlete's words: the monthly cap, a model outage, a server without a model. */
export function aiErrorText(error: unknown, t: (key: Key) => string): string {
  if (error instanceof ApiError) {
    if (error.status === 429 && error.message === "ai_coach_cap_reached") return t("errors.cap");
    if (error.status === 502) return t("errors.failed");
    if (error.status === 503) return t("errors.unavailable");
  }
  return errorMessage(error);
}
