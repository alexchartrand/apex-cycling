import { ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Button, Card } from "../../components/ui";
import type { AiAccess } from "./types";
import { useConsent } from "./useAiCoach";

/** Shown once, before anything is sent to the model provider. */
export function ConsentCard({ athleteId, access }: { athleteId: string; access: AiAccess }) {
  const { t } = useTranslation("aicoach");
  const consent = useConsent(athleteId);
  return (
    <Card as="section" title={t("consent.title")} className="ai-consent">
      <p>{t("consent.intro", { provider: access.provider })}</p>
      <ul>
        <li>{t("consent.sent")}</li>
        <li>{t("consent.health")}</li>
        <li>{t("consent.strava")}</li>
        <li>{t("consent.calendar")}</li>
        <li>{t("consent.withdraw")}</li>
      </ul>
      <p className="ai-muted">{t("consent.notMedical")}</p>
      <div className="ai-row">
        <Button icon={<ShieldCheck aria-hidden />} onClick={() => consent.mutate({ give: true })} loading={consent.isPending}>
          {t("consent.agree")}
        </Button>
      </div>
      {consent.isError && <p className="ai-error">{errorMessage(consent.error)}</p>}
    </Card>
  );
}
