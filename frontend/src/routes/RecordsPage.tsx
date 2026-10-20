import { useState } from "react";
import { Plus, Trophy } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button, EmptyState, PageHeader, SkeletonGroup } from "../components/ui";
import { useActiveAthlete } from "../features/athletes/useActiveAthlete";
import { ManualResultsList } from "../features/records/ManualResultsList";
import { RecordsBoard } from "../features/records/RecordsBoard";
import { entryId, selectionOf } from "../features/records/recordsBoard";
import { RecordTimeline } from "../features/records/RecordTimeline";
import type { RecordEntry } from "../features/records/types";
import { useRecords } from "../features/records/useRecords";
import { useTracks } from "../features/training/useTraining";
import "./RecordsPage.css";

export function RecordsPage() {
  const { t } = useTranslation("records");
  const athleteId = useActiveAthlete().data?.id ?? "";
  const records = useRecords(athleteId);
  const tracks = useTracks(athleteId);
  const [picked, setPicked] = useState<RecordEntry | null>(null);
  const [adding, setAdding] = useState(false);

  const entries = records.data ?? [];
  // Show the first record's history until the athlete picks one; if the picked one
  // is gone (deleted result, excluded lap), fall back to the first again.
  const selected = entries.find((entry) => picked && entryId(entry) === entryId(picked)) ?? entries[0] ?? null;

  return (
    <>
      <PageHeader
        title={t("page.title")}
        description={t("page.description")}
        actions={
          <Button icon={<Plus aria-hidden />} onClick={() => setAdding(true)}>
            {t("page.addResult")}
          </Button>
        }
      />

      {records.isLoading && <SkeletonGroup lines={6} />}
      {records.isError && <p role="alert">{t("page.loadError")}</p>}
      {records.data && entries.length === 0 && (
        <EmptyState icon={<Trophy aria-hidden />} title={t("empty.title")} description={t("empty.description")} />
      )}

      <div className="records-page">
        {entries.length > 0 && (
          <div className="records-page__main">
            <RecordsBoard entries={entries} selectedId={selected ? entryId(selected) : null} onSelect={setPicked} />
            <RecordTimeline athleteId={athleteId} selection={selected ? selectionOf(selected) : null} />
          </div>
        )}
        {tracks.data && !tracks.data.some((track) => track.length_m != null) && tracks.data.length > 0 && (
          <p className="records-page__note">{t("board.needsLength")}</p>
        )}
        <ManualResultsList athleteId={athleteId} tracks={tracks.data ?? []} adding={adding} onAddingChange={setAdding} />
      </div>
    </>
  );
}
