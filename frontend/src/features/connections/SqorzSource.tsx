import { useState, type FormEvent } from "react";
import { CircleStop, Plus, RefreshCw, Radio } from "lucide-react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Badge, Button, Card, Checkbox, ConfirmDialog, Input, useToast } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import type { TransponderAssignment } from "./types";
import {
  useImportTransponderAssignmentNow,
  useReportTransponderUsage,
  useStopTransponderAssignment,
  useTransponderAssignments,
} from "./useConnections";

export function SqorzSource({ athleteId }: { athleteId: string }) {
  const { t } = useTranslation(["import", "common"]);
  const fmt = useFormat();
  const { toast } = useToast();
  const assignments = useTransponderAssignments(athleteId);
  const reportUsage = useReportTransponderUsage(athleteId);
  const importNow = useImportTransponderAssignmentNow(athleteId);
  const stop = useStopTransponderAssignment(athleteId);

  const [transponderCode, setTransponderCode] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [keepSyncing, setKeepSyncing] = useState(true);
  const [formError, setFormError] = useState<string | null>(null);
  const [stopping, setStopping] = useState<TransponderAssignment | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    try {
      await reportUsage.mutateAsync({
        transponder_code: transponderCode.trim().toUpperCase(),
        start_date: startDate,
        end_date: keepSyncing ? null : endDate || null,
      });
      setTransponderCode("");
      setStartDate("");
      setEndDate("");
      toast({ title: t("toasts.added"), description: t("toasts.addedDescription"), tone: "success" });
    } catch (err) {
      setFormError(errorMessage(err));
    }
  }

  async function handleSyncNow(assignment: TransponderAssignment) {
    try {
      const run = await importNow.mutateAsync(assignment.id);
      if (run.status === "success") toast({ title: t("toasts.synced"), description: assignment.transponder_code, tone: "success" });
      else toast({ title: t("toasts.syncFailed"), description: run.error_message ?? undefined, tone: "error" });
    } catch (err) {
      toast({ title: t("toasts.syncFailed"), description: errorMessage(err), tone: "error" });
    }
  }

  async function handleStop() {
    if (!stopping) return;
    try {
      await stop.mutateAsync(stopping.id);
      toast({ title: t("toasts.stopped"), description: stopping.transponder_code });
    } catch (err) {
      toast({ title: errorMessage(err), tone: "error" });
      throw err;
    }
  }

  return (
    <Card eyebrow="my.sqorz.com" title={t("sources.sqorz.title")} actions={<Radio className="import-source__icon" aria-hidden />}>
      <p className="ui-card__hint">{t("sources.sqorz.description")}</p>

      <section className="sqorz__section">
        <h4>{t("assignments.title")}</h4>
        {assignments.data?.length === 0 && <p className="ui-card__hint">{t("assignments.empty")}</p>}
        {assignments.isError && <p role="alert">{t("common:loadError")}</p>}
        {assignments.data && assignments.data.length > 0 && (
          <ul className="sqorz__assignments">
            {assignments.data.map((assignment) => {
              const ongoing = assignment.end_date === null;
              return (
                <li key={assignment.id} className="sqorz__assignment">
                  <div className="sqorz__assignment-main">
                    <span className="sqorz__code">{assignment.transponder_code}</span>
                    {ongoing ? (
                      <Badge tone="positive">{t("assignments.syncing")}</Badge>
                    ) : (
                      <Badge>{t("assignments.ended")}</Badge>
                    )}
                    <span className="sqorz__range">
                      {ongoing
                        ? t("assignments.rangeOngoing", { start: fmt.date(assignment.start_date) })
                        : t("assignments.range", {
                            start: fmt.date(assignment.start_date),
                            end: fmt.date(assignment.end_date),
                          })}
                    </span>
                  </div>
                  <div className="sqorz__assignment-actions">
                    <Button
                      size="sm"
                      variant="secondary"
                      icon={<RefreshCw aria-hidden />}
                      loading={importNow.isPending && importNow.variables === assignment.id}
                      disabled={importNow.isPending}
                      onClick={() => handleSyncNow(assignment)}
                    >
                      {t("assignments.syncNow")}
                    </Button>
                    {ongoing && (
                      <Button size="sm" variant="ghost" icon={<CircleStop aria-hidden />} onClick={() => setStopping(assignment)}>
                        {t("assignments.stop")}
                      </Button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="sqorz__section">
        <h4>{t("form.title")}</h4>
        <form className="sqorz__form" onSubmit={handleSubmit}>
          <Input
            label={t("form.transponder")}
            hint={t("form.transponderHint")}
            value={transponderCode}
            onChange={(e) => setTransponderCode(e.target.value)}
            placeholder="LS-03407"
            autoCapitalize="characters"
            spellCheck={false}
            required
          />
          <Input label={t("form.start")} type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} required />
          <Input
            label={t("form.end")}
            type="date"
            value={endDate}
            min={startDate || undefined}
            onChange={(e) => setEndDate(e.target.value)}
            disabled={keepSyncing}
            required={!keepSyncing}
          />
          <Checkbox className="sqorz__keep" label={t("form.keepSyncing")} checked={keepSyncing} onChange={(e) => setKeepSyncing(e.target.checked)} />
          {formError && <p role="alert" className="sqorz__error">{formError}</p>}
          <Button type="submit" icon={<Plus aria-hidden />} loading={reportUsage.isPending} className="sqorz__submit">
            {t("form.submit")}
          </Button>
        </form>
      </section>

      <ConfirmDialog
        open={stopping !== null}
        onOpenChange={(open) => !open && setStopping(null)}
        title={t("assignments.stopTitle", { code: stopping?.transponder_code ?? "" })}
        description={t("assignments.stopDescription")}
        confirmLabel={t("assignments.stop")}
        cancelLabel={t("common:cancel")}
        tone="danger"
        onConfirm={handleStop}
      />
    </Card>
  );
}
