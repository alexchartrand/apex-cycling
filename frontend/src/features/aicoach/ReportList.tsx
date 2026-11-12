import { FileText, MessageSquare, Sparkles } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Card, EmptyState, SkeletonGroup, StatTile } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { aiErrorText } from "./aiErrors";
import { Markdown } from "./Markdown";
import type { AiReport } from "./types";
import { useReports, useRequestReport } from "./useAiCoach";

function ReportCard({
  report,
  highlighted,
  onDiscuss,
  onProposal,
}: {
  report: AiReport;
  highlighted: boolean;
  onDiscuss?: (conversationId: string) => void;
  onProposal?: (proposalId: string) => void;
}) {
  const { t } = useTranslation("aicoach");
  const fmt = useFormat();
  const { stats } = report;
  const plans = stats.plans;
  return (
    <Card
      as="article"
      className={highlighted ? "ai-report ai-report--highlighted" : "ai-report"}
      eyebrow={
        <>
          {t(`reports.kind.${report.kind}`)} · {fmt.date(report.period_start, "dayMonth")} – {fmt.date(report.period_end, "dayMonth")}
        </>
      }
      actions={report.proposal_id ? <Badge tone="highlight">{t("reports.withProposal")}</Badge> : undefined}
    >
      <div className="ai-report__tiles">
        {plans && plans.total > 0 && <StatTile label={t("reports.stats.plans")} value={`${plans.done}/${plans.total}`} />}
        {stats.actual_tss != null && <StatTile label={t("reports.stats.tss")} value={stats.actual_tss} />}
        {stats.hours != null && <StatTile label={t("reports.stats.hours")} value={fmt.number(stats.hours)} />}
        {stats.avg_rpe != null && <StatTile label={t("reports.stats.rpe")} value={fmt.number(stats.avg_rpe)} />}
        {stats.tsb_end != null && <StatTile label={t("reports.stats.tsb")} value={fmt.number(stats.tsb_end)} />}
      </div>
      <Markdown text={report.content} />
      {(onDiscuss || onProposal) && (
        <div className="ai-report__actions">
          {onProposal && report.proposal_id && (
            <Button size="sm" icon={<Sparkles aria-hidden />} onClick={() => onProposal(report.proposal_id!)}>
              {t("reports.seeProposal")}
            </Button>
          )}
          {onDiscuss && report.conversation_id && (
            <Button size="sm" variant="secondary" icon={<MessageSquare aria-hidden />} onClick={() => onDiscuss(report.conversation_id!)}>
              {t("reports.discuss")}
            </Button>
          )}
        </div>
      )}
    </Card>
  );
}

/** Weekly and on-demand reports, newest first. `canRequest`: the athlete may ask for one now. */
export function ReportList({
  athleteId,
  canRequest,
  highlightId,
  onDiscuss,
  onProposal,
}: {
  athleteId: string;
  canRequest: boolean;
  highlightId?: string | null;
  onDiscuss?: (conversationId: string) => void;
  onProposal?: (proposalId: string) => void;
}) {
  const { t } = useTranslation("aicoach");
  const reports = useReports(athleteId);
  const request = useRequestReport(athleteId);

  return (
    <div className="ai-stack">
      {canRequest && (
        <div className="ai-row">
          <Button icon={<FileText aria-hidden />} onClick={() => request.mutate()} loading={request.isPending}>
            {t("reports.requestNow")}
          </Button>
          {request.isPending && <span className="ai-muted">{t("reports.writing")}</span>}
          {request.isError && <span className="ai-error">{aiErrorText(request.error, t)}</span>}
        </div>
      )}
      {reports.isLoading ? (
        <SkeletonGroup lines={4} />
      ) : (reports.data ?? []).length === 0 ? (
        <EmptyState icon={<FileText aria-hidden />} title={t("reports.none")} description={t("reports.noneHint")} />
      ) : (
        reports.data!.map((report) => (
          <ReportCard
            key={report.id}
            report={report}
            highlighted={report.id === highlightId}
            onDiscuss={onDiscuss}
            onProposal={onProposal}
          />
        ))
      )}
    </div>
  );
}
