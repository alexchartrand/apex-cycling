import { useMemo, useState } from "react";
import { Pencil, Star, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Badge, Card, ConfirmDialog, DataTable, IconButton, Input, Select, useToast, type DataTableColumn } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { parseNumber } from "../tools/toolInputs";
import { withinNoise, worthSeconds } from "./aero";
import type { AeroTest } from "./types";
import { useDeleteAeroTest } from "./useAero";

const DISTANCES_M = [1000, 2000, 3000, 4000];

/** Saved setups side by side: CdA, its difference from a chosen baseline, and what that's worth on the track. */
export function AeroTestsCard({
  athleteId,
  tests,
  editingId,
  onOpen,
}: {
  athleteId: string;
  tests: AeroTest[];
  editingId: string | null;
  onOpen: (test: AeroTest) => void;
}) {
  const { t } = useTranslation("aero");
  const fmt = useFormat();
  const { toast } = useToast();
  const remove = useDeleteAeroTest(athleteId);
  const [chosenBaseline, setChosenBaseline] = useState<string | null>(null);
  const [powerDraft, setPowerDraft] = useState("");
  const [distanceM, setDistanceM] = useState(4000);
  const [deleting, setDeleting] = useState<AeroTest | null>(null);

  const withFit = tests.filter((test) => test.fit !== null);
  const baseline = withFit.find((test) => test.id === chosenBaseline) ?? withFit[0] ?? null;
  const typedPower = parseNumber(powerDraft);
  const powerW = typedPower !== null && typedPower >= 50 && typedPower <= 3000 ? typedPower : Math.round(baseline?.fit?.power_w ?? 400);

  const worth = useMemo(() => {
    const result = new Map<string, number | null>();
    if (!baseline?.fit) return result;
    for (const test of withFit) {
      if (test.id === baseline.id || !test.fit) continue;
      result.set(
        test.id,
        worthSeconds(test.fit.cda_m2, { fit: baseline.fit, conditions: baseline.conditions }, { powerW, distanceM, standing: true }),
      );
    }
    return result;
  }, [baseline, withFit, powerW, distanceM]);

  const setupSummary = (test: AeroTest) => [test.position, test.helmet, test.skinsuit, test.bike].filter(Boolean).join(" · ");

  const columns: DataTableColumn<AeroTest>[] = [
    {
      id: "setup",
      header: t("tests.setup"),
      primary: true,
      cell: (test) => (
        <div className="aero-tests__setup">
          <strong>{test.label}</strong>
          {test.id === baseline?.id && <Badge tone="accent">{t("tests.baseline")}</Badge>}
          {setupSummary(test) && <span className="aero-tests__detail">{setupSummary(test)}</span>}
        </div>
      ),
    },
    {
      id: "session",
      header: t("tests.session"),
      sortValue: (test) => test.event_date,
      cell: (test) => (
        <div className="aero-tests__setup">
          <span>{fmt.date(test.event_date)}</span>
          <span className="aero-tests__detail">
            {test.event_name} · {test.track_name}
          </span>
        </div>
      ),
    },
    {
      id: "cda",
      header: t("tests.cda"),
      align: "right",
      sortValue: (test) => test.fit?.cda_m2 ?? null,
      cell: (test) =>
        test.fit ? (
          <span className="aero-tests__number">
            {fmt.number(test.fit.cda_m2, 3, 3)}
            {test.fit.cda_se_m2 !== null && (
              <span className="aero-tests__detail"> {t("stats.se", { value: fmt.number(test.fit.cda_se_m2, 3, 3) })}</span>
            )}
          </span>
        ) : (
          <span className="aero-tests__detail">{test.problem ? t(`problems.${test.problem}`) : t("tests.noResult")}</span>
        ),
    },
    {
      id: "delta",
      header: t("tests.delta"),
      align: "right",
      cell: (test) => {
        if (!test.fit || !baseline?.fit || test.id === baseline.id) return <span className="aero-tests__detail">—</span>;
        const delta = test.fit.cda_m2 - baseline.fit.cda_m2;
        const percent = (delta / baseline.fit.cda_m2) * 100;
        return (
          <div className="aero-tests__delta">
            <span className="aero-tests__number">
              {delta > 0 ? "+" : delta < 0 ? "−" : "±"}
              {fmt.number(Math.abs(delta), 3, 3)} ({delta < 0 ? "−" : "+"}
              {fmt.number(Math.abs(percent), 1)} %)
            </span>
            {withinNoise(test.fit, baseline.fit) && <span className="aero-tests__detail">{t("tests.noise")}</span>}
          </div>
        );
      },
    },
    {
      id: "worth",
      header: t("tests.worth"),
      align: "right",
      cell: (test) => {
        const seconds = worth.get(test.id);
        if (seconds == null) return <span className="aero-tests__detail">—</span>;
        return (
          <span className={seconds < 0 ? "aero-tests__number aero-tests__gain" : "aero-tests__number aero-tests__loss"}>
            {t("tests.seconds", { value: fmt.deltaSeconds(seconds * 1000, 1) })}
          </span>
        );
      },
    },
    {
      id: "actions",
      header: <span className="visually-hidden">{t("tests.open")}</span>,
      align: "right",
      width: "7.5rem",
      cell: (test) => (
        <div className="aero-tests__actions">
          {test.fit && test.id !== baseline?.id && (
            <IconButton aria-label={t("tests.makeBaseline")} variant="ghost" size="sm" onClick={() => setChosenBaseline(test.id)}>
              <Star aria-hidden />
            </IconButton>
          )}
          <IconButton aria-label={t("tests.open")} variant="ghost" size="sm" onClick={() => onOpen(test)}>
            <Pencil aria-hidden />
          </IconButton>
          <IconButton aria-label={t("tests.delete")} variant="ghost" size="sm" onClick={() => setDeleting(test)}>
            <Trash2 aria-hidden />
          </IconButton>
        </div>
      ),
    },
  ];

  return (
    <Card title={t("tests.title")}>
      {tests.length === 0 ? (
        <p className="ui-card__hint">{t("tests.empty")}</p>
      ) : (
        <>
          {withFit.length > 1 && (
            <div className="aero-tests__scenario">
              <span className="field__label">{t("tests.worthAt")}</span>
              <Input
                className="aero-tests__power"
                aria-label={t("tests.power")}
                suffix="W"
                inputMode="numeric"
                value={powerDraft}
                placeholder={String(powerW)}
                onChange={(e) => setPowerDraft(e.target.value)}
              />
              <Select aria-label={t("tests.distance")} value={distanceM} onChange={(e) => setDistanceM(Number(e.target.value))}>
                {DISTANCES_M.map((d) => (
                  <option key={d} value={d}>
                    {fmt.distance(d)}, {t("tests.standing")}
                  </option>
                ))}
              </Select>
            </div>
          )}
          <DataTable
            columns={columns}
            rows={tests}
            getRowId={(test) => test.id}
            caption={t("tests.caption")}
            selectedRowId={editingId}
          />
        </>
      )}
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={t("tests.confirmDelete", { label: deleting?.label ?? "" })}
        description={t("tests.confirmDeleteBody")}
        confirmLabel={t("tests.delete")}
        cancelLabel={t("save.cancel")}
        tone="danger"
        onConfirm={async () => {
          if (!deleting) return;
          try {
            await remove.mutateAsync(deleting.id);
            toast({ title: t("tests.deleted") });
            setDeleting(null);
          } catch (err) {
            toast({ title: errorMessage(err), tone: "error" });
            throw err;
          }
        }}
      />
    </Card>
  );
}
