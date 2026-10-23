import { Check, ChevronRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Badge, Button, Card, ProgressBar } from "../../components/ui";
import type { Checklist } from "./checklist";
import "./FirstRunChecklist.css";

/** Home: what to set up next, with a "2 of 4" count. Hideable. */
export function FirstRunChecklist({ checklist, onHide }: { checklist: Checklist; onHide: () => void }) {
  const { t } = useTranslation("home");
  return (
    <Card
      as="section"
      eyebrow={t("checklist.eyebrow")}
      title={t("checklist.title")}
      actions={<Badge tone="accent">{t("checklist.progress", { done: checklist.doneCount, total: checklist.total })}</Badge>}
    >
      <ProgressBar value={checklist.doneCount} max={checklist.total} label={t("checklist.progress", { done: checklist.doneCount, total: checklist.total })} />
      <ol className="checklist">
        {checklist.steps.map((step) => (
          <li key={step.key} className={step.done ? "checklist__step checklist__step--done" : "checklist__step"}>
            <span className="checklist__mark" aria-hidden>
              {step.done && <Check />}
            </span>
            <div className="checklist__text">
              <span className="checklist__name">
                {t(`checklist.steps.${step.key}.title`)}
                {step.optional && !step.done && <span className="checklist__optional"> · {t("checklist.optional")}</span>}
                {step.done && <span className="checklist__sr"> ({t("checklist.done")})</span>}
              </span>
              <span className="checklist__hint">{t(`checklist.steps.${step.key}.hint`)}</span>
            </div>
            {!step.done && (
              <Link to={step.to} className="checklist__go">
                {t(`checklist.steps.${step.key}.action`)} <ChevronRight aria-hidden />
              </Link>
            )}
          </li>
        ))}
      </ol>
      <Button variant="ghost" size="sm" onClick={onHide}>
        {t("checklist.hide")}
      </Button>
    </Card>
  );
}
