import { Sparkles } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Card, EmptyState, SkeletonGroup } from "../../components/ui";
import { useAthleteScope } from "../athletes/athleteScope";
import { ProposalList } from "./ProposalList";
import { ReportList } from "./ReportList";
import { useAiAccess } from "./useAiCoach";
import "./AiCoach.css";

/** A coach's look at their athlete's AI coach: reports and proposals, never the athlete's conversations. */
export function CoachAiPanel() {
  const { t } = useTranslation("aicoach");
  const athleteId = useAthleteScope()?.athleteId ?? "";
  const access = useAiAccess(athleteId || undefined);
  if (access.isLoading) return <SkeletonGroup lines={4} />;
  if (!access.data?.enabled) return <EmptyState icon={<Sparkles aria-hidden />} title={t("coachView.off")} />;
  return (
    <div className="ai-stack">
      <p className="ai-muted">{t("coachView.hint")}</p>
      <Card as="section" title={t("tabs.proposals")}>
        <ProposalList athleteId={athleteId} />
      </Card>
      <Card as="section" title={t("tabs.reports")}>
        <ReportList athleteId={athleteId} canRequest={false} />
      </Card>
    </div>
  );
}
