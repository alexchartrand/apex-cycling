import { CalendarPlus, ChevronRight } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Card, SkeletonGroup } from "../../components/ui";
import { localIsoDate } from "../../i18n/format";
import { useFormat } from "../../i18n/useFormat";
import { PlanDetailDialog } from "./PlanDetailDialog";
import { PlanDialog } from "./PlanDialog";
import { outstanding } from "./planForm";
import type { PlannedSession } from "./types";
import { usePlannedSessions } from "./usePlan";
import "./Plan.css";

/** Days back an unanswered plan is still listed (so "did I do Tuesday's session?" isn't lost). */
const OVERDUE_DAYS = 14;

function daysAgo(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return localIsoDate(date);
}

/** Planned sessions still waiting for an answer, with the button to plan another. Hides when empty unless `alwaysShow`. */
export function PlannedSessionsCard({ athleteId, alwaysShow = false }: { athleteId: string; alwaysShow?: boolean }) {
  const { t } = useTranslation("plan");
  const fmt = useFormat();
  const plans = usePlannedSessions(athleteId);
  const [open, setOpen] = useState<PlannedSession | null>(null);
  const [adding, setAdding] = useState(false);
  const today = localIsoDate();
  const waiting = outstanding(plans.data ?? [], daysAgo(OVERDUE_DAYS));

  if (!alwaysShow && !plans.isLoading && waiting.length === 0) return null;

  return (
    <Card
      title={t("title")}
      actions={
        <Button size="sm" variant="secondary" icon={<CalendarPlus aria-hidden />} onClick={() => setAdding(true)}>
          {t("add")}
        </Button>
      }
    >
      {plans.isLoading && <SkeletonGroup lines={2} />}
      {!plans.isLoading && waiting.length === 0 && <p className="plan-empty">{t("empty")}</p>}
      <ul className="plan-list">
        {waiting.map((plan) => (
          <li key={plan.id}>
            <button type="button" className="plan-list__row" onClick={() => setOpen(plan)}>
              <span className="plan-list__date">{fmt.date(plan.planned_date, "weekday")}</span>
              <span className="plan-list__main">
                <span className="plan-list__title">{plan.title}</span>
                {plan.targets.length > 0 && <span className="plan-list__meta">{t("blocks", { count: plan.targets.length })}</span>}
              </span>
              {plan.planned_date < today && <Badge tone="negative">{t("overdue")}</Badge>}
              <ChevronRight className="plan-list__chevron" aria-hidden />
            </button>
          </li>
        ))}
      </ul>

      {adding && <PlanDialog key="new" athleteId={athleteId} date={today} plan={null} onClose={() => setAdding(false)} />}
      {open && <PlanDetailDialog key={open.id} athleteId={athleteId} plan={plans.data?.find((p) => p.id === open.id) ?? open} onClose={() => setOpen(null)} />}
    </Card>
  );
}
