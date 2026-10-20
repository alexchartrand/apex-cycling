import { useTranslation } from "react-i18next";
import { Badge, DataTable, type DataTableColumn } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import type { AeroPoint } from "./types";

/** Every timed lap with what it gives and why it's left out; ticking a lap picks laps by hand. */
export function AeroLapTable({
  points,
  manual,
  onToggle,
}: {
  points: AeroPoint[];
  manual: boolean;
  onToggle: (lapId: string) => void;
}) {
  const { t } = useTranslation("aero");
  const fmt = useFormat();

  const columns: DataTableColumn<AeroPoint>[] = [
    {
      id: "use",
      header: <span className="visually-hidden">{t("laps.use")}</span>,
      width: "2.5rem",
      cell: (p) => (
        <input
          type="checkbox"
          checked={p.used}
          aria-label={`${t("laps.use")} — ${t("chart.lap", { effort: p.effort_index, lap: p.lap_in_effort })}`}
          disabled={p.issue === "excluded" || p.issue === "no_power"}
          onChange={() => onToggle(p.lap_id)}
        />
      ),
    },
    {
      id: "lap",
      header: t("laps.lap"),
      primary: true,
      cell: (p) => t("chart.lap", { effort: p.effort_index, lap: p.lap_in_effort }),
    },
    { id: "time", header: t("laps.time"), align: "right", cell: (p) => fmt.seconds(p.time_s * 1000) },
    { id: "speed", header: t("laps.speed"), align: "right", cell: (p) => fmt.number(p.speed_ms * 3.6, 1, 1) },
    { id: "power", header: t("laps.power"), align: "right", cell: (p) => fmt.number(p.power_w, 0) },
    { id: "cda", header: t("laps.cda"), align: "right", cell: (p) => fmt.number(p.cda_m2, 3, 3) },
    {
      id: "status",
      header: t("laps.status"),
      cell: (p) =>
        p.used ? (
          <Badge tone="positive">{t("laps.used")}</Badge>
        ) : p.issue ? (
          <span className="aero-lab__issue">{t(`laps.issues.${p.issue}`)}</span>
        ) : null,
    },
  ];

  return (
    <>
      <p className="ui-card__hint">{manual ? t("laps.manual") : t("laps.automatic")}</p>
      <div className="aero-lab__laps">
        <DataTable
          columns={columns}
          rows={points}
          getRowId={(p) => p.lap_id}
          caption={t("laps.caption")}
          rowTone={(p) => (p.used ? undefined : "muted")}
          dense
        />
      </div>
    </>
  );
}
