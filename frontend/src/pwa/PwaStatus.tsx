import { RefreshCw, WifiOff } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useRegisterSW } from "virtual:pwa-register/react";
import { Button } from "../components/ui";
import { useOnlineStatus } from "./useOnlineStatus";
import "./PwaStatus.css";

/** Offline banner + "new version available" prompt, rendered by the app shell. */
export function PwaStatus() {
  const { t } = useTranslation("shell");
  const online = useOnlineStatus();
  const {
    needRefresh: [needRefresh, setNeedRefresh],
    updateServiceWorker,
  } = useRegisterSW();

  return (
    <>
      {!online && (
        <div className="pwa-banner pwa-banner--offline" role="status">
          <WifiOff aria-hidden />
          <span>{t("pwa.offline")}</span>
        </div>
      )}
      {needRefresh && (
        <div className="pwa-update" role="alert">
          <RefreshCw aria-hidden className="pwa-update__icon" />
          <span className="pwa-update__text">{t("pwa.updateAvailable")}</span>
          <Button size="sm" variant="ghost" onClick={() => setNeedRefresh(false)}>
            {t("pwa.later")}
          </Button>
          <Button size="sm" onClick={() => updateServiceWorker(true)}>
            {t("pwa.reload")}
          </Button>
        </div>
      )}
    </>
  );
}
