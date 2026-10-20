import { Eye } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useViewingOther } from "../../features/athletes/useActiveAthlete";
import { Button } from "../ui";

/** Shown on every page while looking at someone else's data, so it's never mistaken for your own. */
export function ViewingBanner() {
  const { t } = useTranslation("shell");
  const navigate = useNavigate();
  const { viewing, stopViewing } = useViewingOther();
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
