/** Browser side of Web Push: what the settings page needs to turn it on and off. */

export function pushSupported(): boolean {
  return typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

/** The server's VAPID public key (base64url) as the bytes `subscribe` wants. */
export function urlBase64ToUint8Array(value: string): Uint8Array<ArrayBuffer> {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(value.length / 4) * 4, "=");
  const raw = atob(padded);
  return Uint8Array.from(raw, (char) => char.charCodeAt(0));
}

export async function currentSubscription(): Promise<PushSubscription | null> {
  if (!pushSupported()) return null;
  const registration = await navigator.serviceWorker.getRegistration();
  return registration ? registration.pushManager.getSubscription() : null;
}

/** Asks permission if needed and subscribes this browser. Throws when permission is refused. */
export async function subscribeToPush(publicKey: string): Promise<PushSubscription> {
  const permission = await Notification.requestPermission();
  if (permission !== "granted") throw new PushPermissionError(permission);
  const registration = await navigator.serviceWorker.ready;
  return (
    (await registration.pushManager.getSubscription()) ??
    registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(publicKey) })
  );
}

export class PushPermissionError extends Error {
  permission: NotificationPermission;

  constructor(permission: NotificationPermission) {
    super(`Notification permission ${permission}`);
    this.permission = permission;
  }
}
