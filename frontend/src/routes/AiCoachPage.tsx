import { Sparkles } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import { EmptyState, PageHeader, SkeletonGroup, TabPanel, Tabs, type TabItem } from "../components/ui";
import { ChatPanel } from "../features/aicoach/ChatPanel";
import { CoachProfileForm } from "../features/aicoach/CoachProfileForm";
import { ConsentCard } from "../features/aicoach/ConsentCard";
import { ProposalList } from "../features/aicoach/ProposalList";
import { ReportList } from "../features/aicoach/ReportList";
import { UsageMeter } from "../features/aicoach/UsageMeter";
import { useAiAccess, useProposals } from "../features/aicoach/useAiCoach";
import { useMyAthlete } from "../features/athletes/useAthlete";
import "../features/aicoach/AiCoach.css";

const TABS = ["chat", "proposals", "reports", "profile"] as const;
type Tab = (typeof TABS)[number];

/**
 * The athlete's AI coach (their own data only, never "viewing as"): chat,
 * proposals waiting for an answer, reports and what it knows about them.
 * `?tab=`, `?c=` (open conversation), `?report=`, `?proposal=` are in the URL
 * so notifications can link straight to them.
 */
export function AiCoachPage() {
  const { t } = useTranslation("aicoach");
  const me = useMyAthlete();
  const athleteId = me.data?.id ?? "";
  const access = useAiAccess(athleteId || undefined);
  const pending = useProposals(access.data?.can_use ? athleteId : "", "pending");
  const [params, setParams] = useSearchParams();

  const reportId = params.get("report");
  const proposalId = params.get("proposal");
  const requested = params.get("tab") as Tab | null;
  const tab: Tab = requested && TABS.includes(requested) ? requested : reportId ? "reports" : proposalId ? "proposals" : "chat";
  const conversationId = params.get("c");

  function update(changes: Record<string, string | null>) {
    const next = new URLSearchParams(params);
    for (const [name, value] of Object.entries(changes)) {
      if (value === null) next.delete(name);
      else next.set(name, value);
    }
    setParams(next, { replace: false });
  }

  if (me.isLoading || access.isLoading) return <SkeletonGroup lines={5} />;
  const header = <PageHeader title={t("title")} description={t("description")} actions={access.data?.usage && <UsageMeter usage={access.data.usage} />} />;
  if (!access.data?.available) {
    return (
      <>
        {header}
        <EmptyState icon={<Sparkles aria-hidden />} title={t("unavailable")} description={t("unavailableHint")} />
      </>
    );
  }
  if (!access.data.enabled) {
    return (
      <>
        {header}
        <EmptyState icon={<Sparkles aria-hidden />} title={t("notEnabled")} description={t("notEnabledHint")} />
      </>
    );
  }
  if (!access.data.consented) {
    return (
      <>
        {header}
        <ConsentCard athleteId={athleteId} access={access.data} />
      </>
    );
  }

  const items: TabItem<Tab>[] = TABS.map((value) => ({
    value,
    label: t(`tabs.${value}`),
    count: value === "proposals" && pending.data?.length ? pending.data.length : undefined,
  }));

  return (
    <>
      {header}
      <Tabs items={items} value={tab} onValueChange={(next) => update({ tab: next, report: null, proposal: null })} aria-label={t("tabs.label")}>
        <TabPanel value="chat">
          <ChatPanel athleteId={athleteId} conversationId={conversationId} onOpen={(id) => update({ tab: "chat", c: id })} />
        </TabPanel>
        <TabPanel value="proposals">
          <ProposalList athleteId={athleteId} highlightId={proposalId} onOpenConversation={(id) => update({ tab: "chat", c: id, proposal: null })} />
        </TabPanel>
        <TabPanel value="reports">
          <ReportList
            athleteId={athleteId}
            canRequest
            highlightId={reportId}
            onDiscuss={(id) => update({ tab: "chat", c: id, report: null })}
            onProposal={(id) => update({ tab: "proposals", proposal: id, report: null })}
          />
        </TabPanel>
        <TabPanel value="profile">
          <CoachProfileForm athleteId={athleteId} />
        </TabPanel>
      </Tabs>
    </>
  );
}
