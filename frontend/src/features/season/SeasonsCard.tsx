import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { errorMessage } from "../../api/errors";
import { Badge, Button, Card, ConfirmDialog, DataTable, Dialog, IconButton, Input, Select, SkeletonGroup, StatTile, Tooltip, useToast, type DataTableColumn } from "../../components/ui";
import { localIsoDate } from "../../i18n/format";
import { useFormat } from "../../i18n/useFormat";
import { formatRecordTime } from "../records/timeInput";
import type { StandardEventKey } from "../records/types";
import { defaultSeasonForm, improvementMs, seasonPayload, type SeasonForm } from "./season";
import type { Season, SeasonBest } from "./types";
import { useDeleteSeason, useSaveSeason, useSeasons, useSeasonSummary } from "./useSeason";
import "./Season.css";

/** Season start dates and, for the chosen season, the best at each place and event against what came before. */
export function SeasonsCard({ athleteId }: { athleteId: string }) {
  const { t } = useTranslation("season");
  const { t: tr } = useTranslation("records");
  const { t: tc } = useTranslation("common");
  const fmt = useFormat();
  const { toast } = useToast();
  const seasons = useSeasons(athleteId);
  const remove = useDeleteSeason(athleteId);
  const [picked, setPicked] = useState("");
  const [editing, setEditing] = useState<Season | "new" | null>(null);
  const [deleting, setDeleting] = useState<Season | null>(null);

  // The season in progress until another is picked (the list is newest first).
  const selected = seasons.data?.find((season) => season.id === picked) ?? seasons.data?.find((season) => season.is_current) ?? seasons.data?.[0];
  const summary = useSeasonSummary(athleteId, selected?.id ?? "");

  const columns: DataTableColumn<SeasonBest>[] = [
    {
      id: "event",
      header: t("seasons.event"),
      cell: (best) => `${tr(`events.${best.event_key as StandardEventKey}`)} · ${tr(`startTypes.${best.start_type}`)}`,
      sortValue: (best) => best.event_key,
      primary: true,
    },
    { id: "place", header: t("seasons.place"), cell: (best) => best.place, sortValue: (best) => best.place.toLowerCase(), hideOnMobile: true },
    {
      id: "time",
      header: t("seasons.best"),
      align: "right",
      cell: (best) => (
        <span>
          {formatRecordTime(best.time_ms, fmt)}
          {best.source === "manual" && <Badge>{t("seasons.manual")}</Badge>}
        </span>
      ),
      sortValue: (best) => best.time_ms,
    },
    {
      id: "before",
      header: t("seasons.before"),
      align: "right",
      cell: (best) => (best.previous_best_ms == null ? "—" : formatRecordTime(best.previous_best_ms, fmt)),
      sortValue: (best) => best.previous_best_ms,
      hideOnMobile: true,
    },
    {
      id: "change",
      header: t("seasons.change"),
      align: "right",
      cell: (best) => {
        const gained = improvementMs(best);
        if (gained == null) return <Badge tone="neutral">{t("seasons.first")}</Badge>;
        if (best.improved) return <Badge tone="positive">−{fmt.seconds(gained)} s</Badge>;
        return <span className="season__sub">+{fmt.seconds(-gained)} s</span>;
      },
      sortValue: (best) => improvementMs(best),
    },
    {
      id: "date",
      header: t("seasons.date"),
      cell: (best) =>
        best.external_event_id ? <Link to={`/sessions/${best.external_event_id}`}>{fmt.date(best.achieved_on, "medium")}</Link> : fmt.date(best.achieved_on, "medium"),
      sortValue: (best) => best.achieved_on,
      hideOnMobile: true,
    },
  ];

  return (
    <Card
      title={t("seasons.title")}
      as="section"
      actions={
        <Button size="sm" variant="secondary" icon={<Plus aria-hidden />} onClick={() => setEditing("new")}>
          {t("seasons.add")}
        </Button>
      }
    >
      <p className="season__hint">{t("seasons.description")}</p>
      {seasons.isLoading && <SkeletonGroup lines={3} />}
      {seasons.isError && <p role="alert">{tc("loadError")}</p>}
      {seasons.data?.length === 0 && <p className="season__empty">{t("seasons.empty")}</p>}

      {selected && (
        <div className="season__body">
          <div className="season__picker">
            <Select label={t("seasons.pick")} value={selected.id} onChange={(e) => setPicked(e.target.value)}>
              {seasons.data?.map((season) => (
                <option key={season.id} value={season.id}>
                  {season.name}
                  {season.is_current ? ` — ${t("seasons.current")}` : ""}
                </option>
              ))}
            </Select>
            <span className="season__actions">
              <Tooltip content={t("seasons.edit")}>
                <IconButton size="sm" aria-label={`${t("seasons.edit")} — ${selected.name}`} onClick={() => setEditing(selected)}>
                  <Pencil aria-hidden />
                </IconButton>
              </Tooltip>
              <Tooltip content={t("seasons.remove")}>
                <IconButton size="sm" aria-label={`${t("seasons.remove")} — ${selected.name}`} onClick={() => setDeleting(selected)}>
                  <Trash2 aria-hidden />
                </IconButton>
              </Tooltip>
            </span>
          </div>
          <p className="season__sub">
            {selected.end_date
              ? t("seasons.span", { from: fmt.date(selected.start_date, "medium"), to: fmt.date(selected.end_date, "medium") })
              : t("seasons.since", { from: fmt.date(selected.start_date, "medium") })}
          </p>

          {summary.isLoading && <SkeletonGroup lines={3} />}
          {summary.data && (
            <>
              <div className="season__tiles">
                <StatTile label={t("seasons.sessions")} value={summary.data.sessions} />
                <StatTile label={t("seasons.races")} value={summary.data.races} />
                <StatTile label={t("seasons.bests")} value={summary.data.bests.length} hint={t("seasons.improvedCount", { count: summary.data.bests.filter((b) => b.improved).length })} />
              </div>
              {summary.data.bests.length === 0 ? (
                <p className="season__empty">{t("seasons.noBests")}</p>
              ) : (
                <DataTable
                  caption={t("seasons.caption", { name: selected.name })}
                  columns={columns}
                  rows={summary.data.bests}
                  getRowId={(best) => `${best.place}-${best.event_key}-${best.start_type}`}
                  dense
                />
              )}
            </>
          )}
        </div>
      )}

      {editing && <SeasonDialog key={editing === "new" ? "new" : editing.id} athleteId={athleteId} season={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
      <ConfirmDialog
        open={deleting != null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={t("seasons.delete.title")}
        description={t("seasons.delete.body", { name: deleting?.name ?? "" })}
        confirmLabel={tc("delete")}
        cancelLabel={tc("cancel")}
        tone="danger"
        onConfirm={async () => {
          try {
            await remove.mutateAsync(deleting!.id);
            setPicked("");
            toast({ title: t("seasons.delete.done"), tone: "success" });
          } catch (error) {
            toast({ title: errorMessage(error), tone: "error" });
            throw error;
          }
        }}
      />
    </Card>
  );
}

function SeasonDialog({ athleteId, season, onClose }: { athleteId: string; season: Season | null; onClose: () => void }) {
  const { t } = useTranslation("season");
  const { t: tc } = useTranslation("common");
  const { toast } = useToast();
  const save = useSaveSeason(athleteId);
  const [form, setForm] = useState<SeasonForm>(() => (season ? { name: season.name, start: season.start_date } : defaultSeasonForm(localIsoDate())));
  const [showErrors, setShowErrors] = useState(false);
  const payload = seasonPayload(form);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!payload) {
      setShowErrors(true);
      return;
    }
    try {
      await save.mutateAsync({ id: season?.id, payload });
      toast({ title: t("seasons.saved"), tone: "success" });
      onClose();
    } catch {
      // shown in the form
    }
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={season ? t("seasons.dialog.editTitle") : t("seasons.dialog.addTitle")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {tc("cancel")}
          </Button>
          <Button type="submit" form="season-form" loading={save.isPending}>
            {tc("save")}
          </Button>
        </>
      }
    >
      <form id="season-form" className="season__form" onSubmit={handleSubmit} noValidate>
        <Input
          label={t("seasons.dialog.name")}
          value={form.name}
          maxLength={80}
          autoFocus
          error={showErrors && !form.name.trim() ? t("seasons.dialog.nameInvalid") : undefined}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
        />
        <Input
          label={t("seasons.dialog.start")}
          hint={t("seasons.dialog.startHint")}
          type="date"
          value={form.start}
          error={showErrors && !/^\d{4}-\d{2}-\d{2}$/.test(form.start) ? t("seasons.dialog.startInvalid") : undefined}
          onChange={(e) => setForm({ ...form, start: e.target.value })}
          required
        />
        {save.isError && (
          <p className="season__error" role="alert">
            {errorMessage(save.error)}
          </p>
        )}
      </form>
    </Dialog>
  );
}
