import { CircleAlert, CircleCheck, LoaderCircle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Card } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { useIngestionRuns } from "./useConnections";

const STATUS_ICONS = { success: CircleCheck, pending: LoaderCircle, failed: CircleAlert };

export function SyncActivity({ athleteId, limit = 8 }: { athleteId: string; limit?: number }) {
  const { t } = useTranslation(["import", "common"]);
  const fmt = useFormat();
  const runs = useIngestionRuns(athleteId);

  return (
    <Card title={t("runs.title")}>
      {runs.isError && <p role="alert">{t("common:loadError")}</p>}
      {runs.data?.length === 0 && <p className="ui-card__hint">{t("runs.empty")}</p>}
      {runs.data && runs.data.length > 0 && (
        <ul className="sync-runs">
          {runs.data.slice(0, limit).map((run) => {
            const Icon = STATUS_ICONS[run.status];
            return (
              <li key={run.id} className={`sync-runs__row sync-runs__row--${run.status}`}>
                <Icon aria-hidden className="sync-runs__icon" />
                <div className="sync-runs__text">
                  <span className="sync-runs__title">
                    <span className="sqorz__code">{run.transponder_code}</span> · {t(`runs.${run.status}`)}
                  </span>
                  <span className="sync-runs__when" title={new Date(run.requested_at).toLocaleString(fmt.locale)}>
                    {fmt.relative(run.requested_at)}
                  </span>
                  {run.status === "failed" && run.error_message && <span className="sync-runs__error">{run.error_message}</span>}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
