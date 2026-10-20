import type { Invite } from "./types";

/** Why an invitation no longer works, if it doesn't. */
export function inviteState(
  invite: Pick<Invite, "expires_at" | "max_uses" | "use_count">,
  now: Date = new Date(),
): "active" | "expired" | "used_up" {
  if (new Date(invite.expires_at) <= now) return "expired";
  if (invite.max_uses !== null && invite.use_count >= invite.max_uses) return "used_up";
  return "active";
}
