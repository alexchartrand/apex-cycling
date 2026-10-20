import { Pencil, Trophy } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Badge, Card, DataTable, type DataTableColumn } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { entryId, groupByPlace, isEventKey } from "./recordsBoard";
import { formatRecordTime } from "./timeInput";
import type { RecordEntry } from "./types";
import "./RecordsBoard.css";

/** The records board: one card per track (or manual venue), one row per event and start type. */
export function RecordsBoard({
  entries,
  selectedId,
  onSelect,
}: {
  entries: RecordEntry[];
  selectedId: string | null;
  onSelect: (entry: RecordEntry) => void;
}) {
  const { t } = useTranslation("records");
  const fmt = useFormat();

  const columns: DataTableColumn<RecordEntry>[] = [
    {
      id: "event",
      header: t("board.event"),
      primary: true,
      cell: (entry) => (isEventKey(entry.event_key) ? t(`events.${entry.event_key}`) : entry.event_key),
    },
    { id: "start", header: t("board.start"), cell: (entry) => <Badge tone={entry.start_type === "standing" ? "highlight" : "accent"}>{t(`startTypes.${entry.start_type}`)}</Badge> },
    {
      id: "time",
      header: t("board.time"),
      align: "right",
      cell: (entry) => <strong className="records-board__time">{formatRecordTime(entry.time_ms, fmt)}</strong>,
      sortValue: (entry) => entry.time_ms,
    },
    { id: "date", header: t("board.date"), cell: (entry) => fmt.date(entry.achieved_on, "medium"), sortValue: (entry) => entry.achieved_on },
    {
      id: "source",
      header: t("board.source"),
      cell: (entry) =>
        entry.source === "sqorz" && entry.external_event_id ? (
          <Link className="records-board__link" to={`/sessions/${entry.external_event_id}`} onClick={(e) => e.stopPropagation()}>
            {t("board.session")}
          </Link>
        ) : (
          <span className="records-board__manual">
            <Badge icon={<Pencil aria-hidden />}>{t("board.manual")}</Badge>
            {entry.is_competition && (
              <Badge tone="marker" icon={<Trophy aria-hidden />}>
                {t("board.competition")}
              </Badge>
            )}
          </span>
        ),
    },
  ];

  return (
    <div className="records-board">
      {groupByPlace(entries).map((group) => (
        <Card key={group.key} title={group.place} as="section">
          <DataTable
            caption={t("board.caption", { place: group.place })}
            columns={columns}
            rows={group.entries}
            getRowId={entryId}
            selectedRowId={selectedId}
            onRowClick={onSelect}
            layout="table"
            dense
          />
        </Card>
      ))}
      <p className="records-board__hint">{t("board.selectHint")}</p>
    </div>
  );
}
