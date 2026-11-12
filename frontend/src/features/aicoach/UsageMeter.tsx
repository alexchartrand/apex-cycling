import { useTranslation } from "react-i18next";
import { ProgressBar } from "../../components/ui";
import type { AiUsage } from "./types";

/** This month's share of the athlete's AI budget. */
export function UsageMeter({ usage }: { usage: AiUsage }) {
  const { t } = useTranslation("aicoach");
  const share = usage.monthly_cap > 0 ? Math.min(1, usage.month_tokens / usage.monthly_cap) : 0;
  return (
    <div className="ai-usage" title={t("usage.tooltip")}>
      <span className="ai-muted">{t("usage.label", { percent: Math.round(share * 100) })}</span>
      <ProgressBar value={share} label={t("usage.label", { percent: Math.round(share * 100) })} tone={share >= 0.9 ? "goal" : "accent"} />
    </div>
  );
}
