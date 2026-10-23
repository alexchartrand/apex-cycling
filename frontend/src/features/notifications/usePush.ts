import { useCallback, useEffect, useState } from "react";
import { removePushSubscription, sendPushSubscription } from "./api";
import { currentSubscription, PushPermissionError, pushSupported, subscribeToPush } from "./push";

export type PushState = "unsupported" | "blocked" | "off" | "on";

/** Whether this browser is subscribed to push, and turning that on or off. */
export function usePush(publicKey: string | null) {
  const [state, setState] = useState<PushState>(pushSupported() ? "off" : "unsupported");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    if (!pushSupported()) return setState("unsupported");
    if (Notification.permission === "denied") return setState("blocked");
    setState((await currentSubscription()) ? "on" : "off");
  }, []);

  useEffect(() => {
    // Reads browser state once on mount; enabling/disabling update it themselves.
    void refresh();
  }, [refresh]);

  const enable = useCallback(async () => {
    if (!publicKey) return;
    setBusy(true);
    try {
      const subscription = await subscribeToPush(publicKey);
      await sendPushSubscription(subscription.toJSON());
      setState("on");
    } catch (err) {
      if (err instanceof PushPermissionError) setState(err.permission === "denied" ? "blocked" : "off");
      else throw err;
    } finally {
      setBusy(false);
    }
  }, [publicKey]);

  const disable = useCallback(async () => {
    setBusy(true);
    try {
      const subscription = await currentSubscription();
      if (subscription) {
        await removePushSubscription(subscription.endpoint);
        await subscription.unsubscribe();
      }
      setState("off");
    } finally {
      setBusy(false);
    }
  }, []);

  return { state, busy, enable, disable };
}
