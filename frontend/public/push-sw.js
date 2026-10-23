// Web Push handlers, pulled into the generated service worker (vite.config.ts,
// workbox.importScripts). The server sends { title, body, url, tag }.

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = { body: event.data ? event.data.text() : "" };
  }
  event.waitUntil(
    self.registration.showNotification(data.title || "ApexCycling", {
      body: data.body || "",
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      // One notification per tag, so a retried push replaces instead of stacking.
      tag: data.tag,
      data: { url: data.url },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  // Only paths inside the app: a push payload must never send people elsewhere.
  const requested = event.notification.data && event.notification.data.url;
  const path = typeof requested === "string" && requested.startsWith("/") && !requested.startsWith("//") ? requested : "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(async (windows) => {
      const open = windows.find((client) => "focus" in client);
      if (open) {
        await open.focus();
        if ("navigate" in open) return open.navigate(path);
        return undefined;
      }
      return self.clients.openWindow(path);
    }),
  );
});
