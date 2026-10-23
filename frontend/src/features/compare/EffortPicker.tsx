import { useTranslation } from "react-i18next";
import { Select } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import type { Effort, SessionSummary } from "../training/types";

/** A session and one of its efforts, chosen from two selects. `efforts` is undefined while loading. */
export function EffortPicker({
  title,
  sessions,
  eventId,
  efforts,
  selected,
  onSession,
  onEffort,
}: {
  title: string;
  sessions: SessionSummary[];
  eventId: string;
  efforts: Effort[] | undefined;
  selected: Effort | undefined;
  onSession: (eventId: string) => void;
  onEffort: (firstLapId: string) => void;
}) {
  const { t } = useTranslation("compare");
  const { t: tt } = useTranslation("training");
  const { t: tr } = useTranslation("records");
  const fmt = useFormat();

  return (
    <div className="compare-picker">
      <h2 className="compare-picker__title">{title}</h2>
      <Select label={t("session")} value={eventId} onChange={(e) => onSession(e.target.value)}>
        {eventId === "" && <option value="">{t("chooseSession")}</option>}
        {sessions.map((session) => (
          <option key={session.external_event_id} value={session.external_event_id}>
            {fmt.date(session.event_date, "medium")} · {session.event_name}
          </option>
        ))}
      </Select>
      <Select
        label={t("effort")}
        value={selected?.lap_ids[0] ?? ""}
        disabled={!efforts || efforts.length === 0}
        onChange={(e) => onEffort(e.target.value)}
      >
        {(efforts ?? []).map((effort) => (
          <option key={effort.lap_ids[0]} value={effort.lap_ids[0]}>
            {effort.label ?? tt("efforts.effortN", { n: effort.index })} · {tr(`startTypes.${effort.start_type}`)} ·{" "}
            {tt("efforts.lapsDone", { done: effort.completed_lap_count, total: effort.lap_ids.length })}
            {effort.total_time_ms != null ? ` · ${fmt.lapTime(effort.total_time_ms)}` : ""}
          </option>
        ))}
      </Select>
    </div>
  );
}
