import { Trash2 } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from "recharts";
import { errorMessage } from "../../api/errors";
import { axisProps, ChartFrame, ChartTooltip, cursorProps, gridProps } from "../../components/charts";
import {
  Button,
  Card,
  ConfirmDialog,
  DataTable,
  IconButton,
  Input,
  StatTile,
  useToast,
  type DataTableColumn,
} from "../../components/ui";
import { localIsoDate, parseLocalDate } from "../../i18n/format";
import { useFormat } from "../../i18n/useFormat";
import { METRIC_FIELDS, type AthleteMetric, type AthleteMetricPayload, type MetricField } from "../athletes/types";
import { useCurrentMetrics, useDeleteMetric, useMetricsHistory, useRecordMetrics } from "../athletes/useAthlete";

const LABEL_KEYS = {
  weight_kg: "physiology.weight",
  ftp_w: "physiology.ftp",
  max_hr: "physiology.maxHr",
  resting_hr: "physiology.restingHr",
} as const satisfies Record<MetricField, string>;

const UNIT_KEYS = {
  weight_kg: "units.kg",
  ftp_w: "units.w",
  max_hr: "units.bpm",
  resting_hr: "units.bpm",
} as const satisfies Record<MetricField, string>;

// Input bounds mirror the backend's AthleteMetricWrite validation.
const INPUT_BOUNDS: Record<MetricField, { min: number; max: number; step: number }> = {
  weight_kg: { min: 20.1, max: 249.9, step: 0.1 },
  ftp_w: { min: 1, max: 2499, step: 1 },
  max_hr: { min: 80, max: 250, step: 1 },
  resting_hr: { min: 20, max: 150, step: 1 },
};

const EMPTY_FORM: Record<MetricField, string> = { weight_kg: "", ftp_w: "", max_hr: "", resting_hr: "" };

export function PhysiologySettings({ athleteId }: { athleteId: string }) {
  const { t } = useTranslation("settings");
  const { t: tc } = useTranslation("common");
  const fmt = useFormat();
  const { toast } = useToast();
  const current = useCurrentMetrics(athleteId);
  const history = useMetricsHistory(athleteId);
  const record = useRecordMetrics(athleteId);
  const remove = useDeleteMetric(athleteId);

  const [date, setDate] = useState(localIsoDate);
  const [values, setValues] = useState(EMPTY_FORM);
  const [pendingDelete, setPendingDelete] = useState<AthleteMetric | null>(null);
  const hasValue = METRIC_FIELDS.some((field) => values[field] !== "");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!hasValue) return;
    const payload: AthleteMetricPayload = { effective_date: date };
    for (const field of METRIC_FIELDS) {
      if (values[field] !== "") payload[field] = Number(values[field]);
    }
    try {
      await record.mutateAsync(payload);
      setValues(EMPTY_FORM);
      toast({ title: t("physiology.add.saved"), tone: "success" });
    } catch {
      // surfaced via record.error below
    }
  }

  const weightPoints = useMemo(
    () =>
      (history.data ?? [])
        .filter((row) => row.weight_kg != null)
        .map((row) => ({ t: parseLocalDate(row.effective_date).getTime(), weight: row.weight_kg }))
        .sort((a, b) => a.t - b.t),
    [history.data],
  );

  const weight = current.data?.weight_kg;
  const ftp = current.data?.ftp_w;

  const formatValue = (field: MetricField, value: number | null | undefined) =>
    field === "weight_kg" ? fmt.number(value, 1, 1) : fmt.number(value, 0);

  const columns: DataTableColumn<AthleteMetric>[] = [
    {
      id: "date",
      header: t("physiology.date"),
      cell: (row) => fmt.date(row.effective_date, "medium"),
      sortValue: (row) => row.effective_date,
      primary: true,
    },
    ...METRIC_FIELDS.map(
      (field): DataTableColumn<AthleteMetric> => ({
        id: field,
        header: `${t(LABEL_KEYS[field])} (${tc(UNIT_KEYS[field])})`,
        cell: (row) => formatValue(field, row[field]),
        sortValue: (row) => row[field],
        align: "right",
      }),
    ),
    {
      id: "actions",
      header: <span className="visually-hidden">{tc("delete")}</span>,
      cell: (row) => (
        <IconButton
          size="sm"
          aria-label={t("physiology.deleteLabel", { date: fmt.date(row.effective_date, "medium") })}
          onClick={(e) => {
            e.stopPropagation();
            setPendingDelete(row);
          }}
        >
          <Trash2 aria-hidden />
        </IconButton>
      ),
      align: "right",
      width: "3rem",
    },
  ];

  return (
    <>
      <Card title={t("physiology.title")} as="section">
        <p className="settings-section__description">{t("physiology.description")}</p>
        <div className="settings-tiles">
          {METRIC_FIELDS.map((field) => {
            const dated = current.data?.[field];
            const wkg =
              field === "ftp_w" && ftp && weight ? t("physiology.wkgHint", { value: fmt.number(ftp.value / weight.value, 2, 2) }) : null;
            return (
              <StatTile
                key={field}
                label={t(LABEL_KEYS[field])}
                value={dated ? formatValue(field, dated.value) : "—"}
                unit={dated ? tc(UNIT_KEYS[field]) : undefined}
                hint={
                  dated ? (
                    <>
                      {wkg && <span className="settings-tiles__wkg">{wkg} · </span>}
                      {t("physiology.asOf", { date: fmt.date(dated.effective_date, "medium") })}
                    </>
                  ) : (
                    t("physiology.notRecorded")
                  )
                }
              />
            );
          })}
        </div>
      </Card>

      <Card title={t("physiology.add.title")} as="section">
        <form className="settings-form" onSubmit={handleSubmit}>
          <p className="settings-section__description">{t("physiology.add.hint")}</p>
          <div className="settings-form__grid settings-form__grid--metrics">
            <Input
              label={t("physiology.add.date")}
              type="date"
              value={date}
              max={localIsoDate()}
              onChange={(e) => setDate(e.target.value)}
              required
            />
            {METRIC_FIELDS.map((field) => (
              <Input
                key={field}
                label={t(LABEL_KEYS[field])}
                type="number"
                inputMode={field === "weight_kg" ? "decimal" : "numeric"}
                {...INPUT_BOUNDS[field]}
                suffix={tc(UNIT_KEYS[field])}
                value={values[field]}
                onChange={(e) => setValues((prev) => ({ ...prev, [field]: e.target.value }))}
              />
            ))}
          </div>
          {record.error && <p role="alert" className="settings-form__error">{errorMessage(record.error)}</p>}
          <div className="settings-form__actions">
            <Button type="submit" loading={record.isPending} disabled={!hasValue || !date}>
              {t("physiology.add.submit")}
            </Button>
          </div>
        </form>
      </Card>

      <Card title={t("physiology.weightChart")} as="section">
        <ChartFrame height={180} isEmpty={weightPoints.length < 2} emptyMessage={t("physiology.weightChartEmpty")}>
          <LineChart data={weightPoints} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid {...gridProps} />
            <XAxis
              dataKey="t"
              type="number"
              scale="time"
              domain={["dataMin", "dataMax"]}
              tickFormatter={(value: number) => fmt.date(new Date(value), "dayMonth")}
              minTickGap={32}
              {...axisProps}
            />
            <YAxis
              domain={[(min: number) => Math.floor(min - 1), (max: number) => Math.ceil(max + 1)]}
              tickFormatter={(kg: number) => fmt.number(kg, 0)}
              width={40}
              {...axisProps}
            />
            <Tooltip
              cursor={cursorProps}
              content={
                <ChartTooltip
                  formatValue={(kg) => `${fmt.number(kg, 1, 1)} ${tc("units.kg")}`}
                  formatLabel={(value) => fmt.date(new Date(Number(value)), "medium")}
                />
              }
            />
            <Line
              type="linear"
              dataKey="weight"
              name={t("physiology.weight")}
              stroke="var(--chart-1)"
              strokeWidth={2}
              dot={{ r: 3, fill: "var(--chart-1)", strokeWidth: 0 }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ChartFrame>
      </Card>

      <Card title={t("physiology.history")} as="section" padding="flush">
        <DataTable
          columns={columns}
          rows={history.data ?? []}
          getRowId={(row) => row.id}
          caption={t("physiology.history")}
          initialSort={{ columnId: "date", direction: "desc" }}
          empty={t("physiology.historyEmpty")}
          dense
        />
      </Card>

      <ConfirmDialog
        open={pendingDelete != null}
        onOpenChange={(open) => !open && setPendingDelete(null)}
        title={t("physiology.deleteConfirm.title")}
        description={
          pendingDelete
            ? t("physiology.deleteConfirm.description", { date: fmt.date(pendingDelete.effective_date, "medium") })
            : undefined
        }
        confirmLabel={t("physiology.deleteConfirm.confirm")}
        cancelLabel={tc("cancel")}
        tone="danger"
        onConfirm={async () => {
          if (!pendingDelete) return;
          try {
            await remove.mutateAsync(pendingDelete.id);
            toast({ title: t("physiology.deleted"), tone: "success" });
          } catch (error) {
            toast({ title: errorMessage(error), tone: "error" });
            throw error;
          }
        }}
      />
    </>
  );
}
