import { useState } from "react";
import { ArrowRight, CalendarMinus, CalendarPlus, CalendarX, Pencil, Sparkles, TriangleAlert } from "lucide-react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Badge, Button, type BadgeTone } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { IntensityChart } from "../workouts/IntensityChart";
import { clockText } from "../workouts/profile";
import { Markdown } from "./Markdown";
import { warningKey } from "./proposalText";
import type { Proposal, ProposalItem, ProposalStatus } from "./types";
import { useDecideProposal } from "./useAiCoach";

const STATUS_TONE: Record<ProposalStatus, BadgeTone> = {
  pending: "highlight",
  accepted: "positive",
  rejected: "neutral",
  superseded: "neutral",
  expired: "neutral",
};

const OP_ICON = { create: CalendarPlus, update: Pencil, skip: CalendarMinus, delete: CalendarX } as const;

function ItemRow({ item, expanded }: { item: ProposalItem; expanded: boolean }) {
  const { t } = useTranslation("aicoach");
  const fmt = useFormat();
  const Icon = OP_ICON[item.op];
  const before = item.before;
  const date = item.planned_date ?? before?.planned_date ?? null;
  const moved = before && item.planned_date && before.planned_date !== item.planned_date;
  return (
    <li className={`ai-proposal__item ai-proposal__item--${item.op}`}>
      <Icon aria-hidden className="ai-proposal__icon" />
      <div className="ai-proposal__body">
        <div className="ai-proposal__line">
          <span className="ai-proposal__op">{t(`proposal.op.${item.op}`)}</span>
          <span className="ai-proposal__date">
            {moved ? (
              <>
                {fmt.date(before.planned_date, "weekday")} <ArrowRight aria-hidden className="ai-inline-icon" />{" "}
                {fmt.date(item.planned_date!, "weekday")}
              </>
            ) : (
              date && fmt.date(date, "weekday")
            )}
          </span>
        </div>
        <div className="ai-proposal__title">
          {item.op === "skip" || item.op === "delete" ? before?.title : item.title}
          {item.op === "update" && before && item.title && before.title !== item.title && (
            <span className="ai-muted"> ({t("proposal.was", { title: before.title })})</span>
          )}
        </div>
        {item.estimate && (
          <div className="ai-muted">
            {item.workout_name && <>{item.workout_name} · </>}
            {clockText(item.estimate.duration_s)}
            {item.estimate.tss != null && <> · {t("proposal.tss", { value: Math.round(item.estimate.tss) })}</>}
          </div>
        )}
        {item.reason && <div className="ai-muted">{item.reason}</div>}
        {item.warnings.map((warning) => (
          <Badge key={warning} tone="marker">
            <TriangleAlert aria-hidden className="ai-inline-icon" /> {t(`proposal.warnings.${warningKey(warning)}`)}
          </Badge>
        ))}
        {expanded && item.description && <Markdown text={item.description} className="ai-proposal__description" />}
        {expanded && item.estimate && item.estimate.segments.length > 0 && <IntensityChart segments={item.estimate.segments} />}
      </div>
    </li>
  );
}

/** A set of calendar changes the AI coach proposes; nothing changes until the athlete accepts. */
export function ProposalCard({ athleteId, proposal, compact = false }: { athleteId: string; proposal: Proposal; compact?: boolean }) {
  const { t } = useTranslation("aicoach");
  const fmt = useFormat();
  const decide = useDecideProposal(athleteId);
  const [expanded, setExpanded] = useState(false);
  const [showAll, setShowAll] = useState(!compact);
  const items = showAll ? proposal.items : proposal.items.slice(0, 4);
  const pending = proposal.status === "pending";
  const overHours = proposal.warnings.filter((w) => w.startsWith("over_hours:")).map((w) => w.slice("over_hours:".length));

  return (
    <article className="ai-proposal" aria-label={t("proposal.label")}>
      <header className="ai-proposal__header">
        <Sparkles aria-hidden className="ai-proposal__spark" />
        <span className="ai-proposal__kind">{t(`proposal.kind.${proposal.kind}`)}</span>
        <Badge tone={STATUS_TONE[proposal.status]}>{t(`proposal.status.${proposal.status}`)}</Badge>
      </header>
      <Markdown text={proposal.summary} />
      {proposal.goal && (
        <p className="ai-proposal__goal">
          <strong>{t("proposal.goal")}</strong> {proposal.goal}
        </p>
      )}

      {proposal.weeks.length > 0 && (
        <div className="ai-proposal__weeks" role="list" aria-label={t("proposal.weeks")}>
          {proposal.weeks.map((week) => (
            <div key={week.week_start} role="listitem" className={overHours.includes(week.week_start) ? "ai-week ai-week--over" : "ai-week"}>
              <span className="ai-week__label">{t("proposal.weekOf", { date: fmt.date(week.week_start, "dayMonth") })}</span>
              <span>{t("proposal.sessions", { count: week.sessions })}</span>
              <span>{clockText(week.duration_s)}</span>
              {week.tss != null && <span>{t("proposal.tss", { value: Math.round(week.tss) })}</span>}
            </div>
          ))}
        </div>
      )}

      {items.length > 0 && (
        <ol className="ai-proposal__items">
          {items.map((item, index) => (
            <ItemRow key={`${item.plan_id ?? "new"}-${index}`} item={item} expanded={expanded} />
          ))}
        </ol>
      )}
      <div className="ai-proposal__toggles">
        {proposal.items.length > items.length && (
          <Button variant="ghost" size="sm" onClick={() => setShowAll(true)}>
            {t("proposal.showAll", { count: proposal.items.length })}
          </Button>
        )}
        {proposal.items.some((i) => i.estimate) && (
          <Button variant="ghost" size="sm" onClick={() => setExpanded((v) => !v)}>
            {expanded ? t("proposal.hideWorkouts") : t("proposal.showWorkouts")}
          </Button>
        )}
      </div>

      {proposal.outline.length > 0 && (
        <details className="ai-proposal__outline">
          <summary>{t("proposal.outline", { count: proposal.outline.length })}</summary>
          <ol>
            {proposal.outline.map((week) => (
              <li key={week.week_start}>
                <strong>{t("proposal.weekOf", { date: fmt.date(week.week_start, "dayMonth") })}</strong> · {week.focus}
                {week.hours != null && <> · {t("proposal.hours", { value: fmt.number(week.hours) })}</>}
                {week.notes && <div className="ai-muted">{week.notes}</div>}
              </li>
            ))}
          </ol>
        </details>
      )}

      {pending && proposal.errors.length > 0 && (
        <div className="ai-proposal__errors" role="alert">
          <strong>{t("proposal.stale")}</strong>
          <ul>
            {proposal.errors.map((error) => (
              <li key={error}>{error}</li>
            ))}
          </ul>
        </div>
      )}

      {pending && proposal.can_decide && (
        <footer className="ai-proposal__actions">
          <Button
            onClick={() => decide.mutate({ id: proposal.id, decision: "accept" })}
            loading={decide.isPending && decide.variables?.decision === "accept"}
            disabled={decide.isPending || proposal.errors.length > 0}
          >
            {t("proposal.accept")}
          </Button>
          <Button
            variant="secondary"
            onClick={() => decide.mutate({ id: proposal.id, decision: "reject" })}
            loading={decide.isPending && decide.variables?.decision === "reject"}
            disabled={decide.isPending}
          >
            {t("proposal.reject")}
          </Button>
          <span className="ai-muted">{t("proposal.expires", { date: fmt.date(proposal.expires_at, "dayMonth") })}</span>
        </footer>
      )}
      {decide.isError && <p className="ai-error">{errorMessage(decide.error, { 409: t("proposal.conflict") })}</p>}
    </article>
  );
}
