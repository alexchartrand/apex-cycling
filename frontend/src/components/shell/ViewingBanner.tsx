import { useEffect } from "react";
import { Eye } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useViewingOther } from "../../features/athletes/useActiveAthlete";
import { useSwitchOptionsState } from "../../features/athletes/useSwitchOptions";
import { Button } from "../ui";

/** Shown on every page while looking at someone else's data, so it's never mistaken for your own. */
export function ViewingBanner() {
  const { t } = useTranslation("shell");
  const navigate = useNavigate();
  const { viewing, stopViewing } = useViewingOther();
  const switchable = useSwitchOptionsState();
  // Coaches used to switch to their athletes; such a switch left in the tab is
  // no longer one (they read them under /coach/athletes/:id), so drop it.
  const stale = viewing !== undefined && !switchable.loading && !switchable.options.some((o) => o.athleteId === viewing.id);
  useEffect(() => {
    if (stale) stopViewing();
  }, [stale, stopViewing]);
  if (!viewing) return null;

  return (
    <div className="shell__viewing" role="status">
      <Eye aria-hidden />
      <span className="shell__viewing-text">{t("viewing.banner", { name: viewing.display_name })}</span>
      <Button
        size="sm"
        variant="secondary"
        onClick={() => {
          stopViewing();
          navigate("/");
        }}
      >
        {t("viewing.back")}
      </Button>
    </div>
  );
}
