import { useEffect, useRef } from "react";
import { MessageSquare, Sparkles } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button, EmptyState, SkeletonGroup } from "../../components/ui";
import { ProposalCard } from "./ProposalCard";
import { useProposals } from "./useAiCoach";

/** Proposals, the waiting ones first. Read-only for a coach (`can_decide` is false for them). */
export function ProposalList({
  athleteId,
  highlightId,
  onOpenConversation,
}: {
  athleteId: string;
  highlightId?: string | null;
  onOpenConversation?: (conversationId: string) => void;
}) {
  const { t } = useTranslation("aicoach");
  const proposals = useProposals(athleteId);
  const highlighted = useRef<HTMLDivElement>(null);

  useEffect(() => {
    highlighted.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  }, [highlightId, proposals.data]);

  if (proposals.isLoading) return <SkeletonGroup lines={4} />;
  const rows = [...(proposals.data ?? [])].sort((a, b) => Number(b.status === "pending") - Number(a.status === "pending"));
  if (rows.length === 0) {
    return <EmptyState icon={<Sparkles aria-hidden />} title={t("proposals.none")} description={t("proposals.noneHint")} />;
  }
  return (
    <div className="ai-stack">
      {rows.map((proposal) => (
        <div
          key={proposal.id}
          ref={proposal.id === highlightId ? highlighted : undefined}
          className={proposal.id === highlightId ? "ai-highlight" : undefined}
        >
          <ProposalCard athleteId={athleteId} proposal={proposal} />
          {onOpenConversation && proposal.conversation_id && (
            <Button
              variant="ghost"
              size="sm"
              icon={<MessageSquare aria-hidden />}
              onClick={() => onOpenConversation(proposal.conversation_id!)}
            >
              {t("proposals.openConversation")}
            </Button>
          )}
        </div>
      ))}
    </div>
  );
}
