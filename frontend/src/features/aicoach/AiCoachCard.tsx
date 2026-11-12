import { Sparkles } from "lucide-react";
import { useTranslation } from "react-i18next";
import { ButtonLink, Card } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { headline } from "./reportText";
import { useAiAccess, useProposals, useReports } from "./useAiCoach";
import "./AiCoach.css";

/** Home: what the AI coach has waiting (proposals) and its latest report. Only the athlete themself sees it. */
export function AiCoachCard({ athleteId }: { athleteId: string }) {
  const { t } = useTranslation("aicoach");
  const fmt = useFormat();
  const access = useAiAccess(athleteId);
  const canUse = !!access.data?.can_use;
  const pending = useProposals(canUse ? athleteId : "", "pending");
  const reports = useReports(athleteId, canUse);
  if (!canUse) return null;

  const waiting = pending.data ?? [];
  const latest = reports.data?.[0];
  return (
    <Card title={t("home.title")} actions={<Sparkles className="home__card-icon" aria-hidden />}>
      <div className="ai-stack ai-stack--tight">
        {waiting.length > 0 && (
          <div className="ai-row ai-row--between">
            <span>
              <strong>{t("home.pending", { count: waiting.length })}</strong>
              <span className="ai-muted"> · {waiting[0].summary.slice(0, 120)}</span>
            </span>
            <ButtonLink to={`/ai-coach?tab=proposals&proposal=${waiting[0].id}`} size="sm">
              {t("home.review")}
            </ButtonLink>
          </div>
        )}
        {latest && (
          <div className="ai-row ai-row--between">
            <span>
              <span className="ai-muted">{t("home.report", { date: fmt.date(latest.period_end, "dayMonth") })} · </span>
              {headline(latest.content)}
            </span>
            <ButtonLink to={`/ai-coach?tab=reports&report=${latest.id}`} size="sm" variant="secondary">
              {t("home.read")}
            </ButtonLink>
          </div>
        )}
        {waiting.length === 0 && !latest && (
          <div className="ai-row ai-row--between">
            <span className="ai-muted">{t("home.empty")}</span>
            <ButtonLink to="/ai-coach" size="sm">
              {t("home.open")}
            </ButtonLink>
          </div>
        )}
      </div>
    </Card>
  );
}
