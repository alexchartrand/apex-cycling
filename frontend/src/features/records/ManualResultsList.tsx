import { useState } from "react";
import { Pencil, Trash2, Trophy } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Badge, Card, ConfirmDialog, DataTable, IconButton, Tooltip, useToast, type DataTableColumn } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { ManualResultDialog } from "./ManualResultDialog";
import { formatRecordTime } from "./timeInput";
import type { TrackSummary } from "../training/types";
import type { ManualResult, StandardEventKey } from "./types";
import { useDeleteManualResult, useManualResults } from "./useRecords";
import "./ManualResultsList.css";

/** The results the athlete typed in, with edit and delete. The dialog to add one is opened by the page. */
export function ManualResultsList({
  athleteId,
  tracks,
  adding,
  onAddingChange,
}: {
  athleteId: string;
  tracks: TrackSummary[];
  adding: boolean;
  onAddingChange: (adding: boolean) => void;
}) {
  const { t } = useTranslation("records");
  const { t: tc } = useTranslation("common");
  const fmt = useFormat();
  const { toast } = useToast();
  const results = useManualResults(athleteId);
  const remove = useDeleteManualResult(athleteId);
  const [editing, setEditing] = useState<ManualResult | null>(null);
  const [deleting, setDeleting] = useState<ManualResult | null>(null);

  const eventLabel = (result: ManualResult) =>
    `${t(`events.${result.event_key as StandardEventKey}`)} · ${t(`startTypes.${result.start_type}`)}`;

  const columns: DataTableColumn<ManualResult>[] = [
    { id: "result", header: t("manual.result"), primary: true, cell: (r) => eventLabel(r) },
    { id: "time", header: t("board.time"), align: "right", cell: (r) => <strong>{formatRecordTime(r.time_ms, fmt)}</strong>, sortValue: (r) => r.time_ms },
    { id: "date", header: t("board.date"), cell: (r) => fmt.date(r.achieved_on, "medium"), sortValue: (r) => r.achieved_on },
    {
      id: "place",
      header: t("manual.place"),
      cell: (r) => (
        <span className="manual-list__place">
          {r.place}
          {r.is_competition && (
            <Badge tone="marker" icon={<Trophy aria-hidden />}>
              {t("board.competition")}
            </Badge>
          )}
        </span>
      ),
    },
    {
      id: "actions",
      header: <span className="visually-hidden">{t("manual.actions")}</span>,
      align: "right",
      width: "6rem",
      cell: (r) => (
        <span className="manual-list__actions">
          <Tooltip content={t("manual.edit")}>
            <IconButton size="sm" aria-label={`${t("manual.edit")} — ${eventLabel(r)}, ${fmt.date(r.achieved_on, "medium")}`} onClick={() => setEditing(r)}>
              <Pencil aria-hidden />
            </IconButton>
          </Tooltip>
          <Tooltip content={t("manual.delete")}>
            <IconButton size="sm" aria-label={`${t("manual.delete")} — ${eventLabel(r)}, ${fmt.date(r.achieved_on, "medium")}`} onClick={() => setDeleting(r)}>
              <Trash2 aria-hidden />
            </IconButton>
          </Tooltip>
        </span>
      ),
    },
  ];

  return (
    <Card as="section" title={t("manual.title")}>
      <p className="manual-list__description">{t("manual.description")}</p>
      {results.isError && <p role="alert">{t("page.loadError")}</p>}
      {results.data && (
        <DataTable
          caption={t("manual.caption")}
          columns={columns}
          rows={results.data}
          getRowId={(r) => r.id}
          initialSort={{ columnId: "date", direction: "desc" }}
          empty={<p className="manual-list__description">{t("manual.empty")}</p>}
          dense
        />
      )}

      {(adding || editing) && (
        <ManualResultDialog
          key={editing?.id ?? "new"}
          athleteId={athleteId}
          tracks={tracks}
          result={editing}
          onClose={() => {
            setEditing(null);
            onAddingChange(false);
          }}
        />
      )}
      <ConfirmDialog
        open={deleting != null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={t("manual.deleteTitle")}
        description={
          deleting
            ? t("manual.deleteDescription", {
                event: eventLabel(deleting),
                time: formatRecordTime(deleting.time_ms, fmt),
                date: fmt.date(deleting.achieved_on, "medium"),
              })
            : undefined
        }
        confirmLabel={t("manual.deleteConfirm")}
        cancelLabel={tc("cancel")}
        tone="danger"
        onConfirm={async () => {
          if (!deleting) return;
          await remove.mutateAsync(deleting.id);
          toast({ title: t("manual.deleted"), tone: "success" });
        }}
      />
    </Card>
  );
}
