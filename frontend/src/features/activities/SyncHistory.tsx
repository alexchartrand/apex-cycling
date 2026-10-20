import { CircleAlert, CircleCheck, LoaderCircle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useFormat } from "../../i18n/useFormat";
import type { SyncRun } from "./types";

const ICONS = { success: CircleCheck, pending: LoaderCircle, failed: CircleAlert };

/** The last few sync runs of one connection. */
export function SyncHistory({ runs, limit = 4 }: { runs: SyncRun[]; limit?: number }) {
  const { t } = useTranslation("activities");
  const fmt = useFormat();
  return (
    <section className="sync-history">
      <h5>{t("history.title")}</h5>
      {runs.length === 0 && <p className="source-card__note">{t("history.empty")}</p>}
      <ul className="sync-runs">
        {runs.slice(0, limit).map((run) => {
          const Icon = ICONS[run.status];
          const summary =
            run.status === "failed"
              ? t("history.failed")
              : run.status === "pending"
                ? t("history.pending")
                : run.imported_count
                  ? t("history.imported", { count: run.imported_count })
                  : t("history.nothingNew");
          return (
            <li key={run.requested_at} className={`sync-runs__row sync-runs__row--${run.status}`}>
              <Icon aria-hidden className="sync-runs__icon" />
              <div className="sync-runs__text">
                <span className="sync-runs__title">{summary}</span>
                <span className="sync-runs__when" title={new Date(run.requested_at).toLocaleString(fmt.locale)}>
                  {fmt.relative(run.requested_at)}
                </span>
                {run.status === "failed" && run.error_message && <span className="sync-runs__error">{run.error_message}</span>}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
