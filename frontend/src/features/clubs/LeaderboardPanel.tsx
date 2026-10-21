import { Trophy } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Badge, Card, DataTable, EmptyState, Select, SkeletonGroup, type DataTableColumn } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { ageCategoryLabel } from "../athletes/ageCategory";
import { useMyAthlete } from "../athletes/useAthlete";
import { formatRecordTime } from "../records/timeInput";
import { EVENT_START_TYPES, STANDARD_EVENT_KEYS, type StandardEventKey } from "../records/types";
import type { Club, LeaderboardEntry, LeaderboardQuery } from "./types";
import { useClubTracks, useLeaderboard } from "./useClubs";

/**
 * The best time of each athlete who opted in, on one of the club's tracks: pick the event,
 * the start, the track, and optionally a sex and an age category.
 */
export function LeaderboardPanel({ club }: { club: Club }) {
  const { t } = useTranslation("club");
  const { t: tr } = useTranslation("records");
  const { t: tc } = useTranslation("common");
  const fmt = useFormat();
  const tracks = useClubTracks(club.id);
  const me = useMyAthlete();
  const [eventKey, setEventKey] = useState<StandardEventKey>("1km");
  const [startType, setStartType] = useState<"standing" | "flying">("standing");
  const [trackId, setTrackId] = useState("");
  const [sex, setSex] = useState<LeaderboardQuery["sex"]>("");
  const [category, setCategory] = useState("");

  // The first track of the club's facilities until another is picked.
  const selectedTrackId = trackId || tracks.data?.[0]?.id || "";
  const query: LeaderboardQuery = { eventKey, startType, trackId: selectedTrackId, sex, category };
  const board = useLeaderboard(club.id, selectedTrackId ? query : null);

  // A category chosen before the filters changed may no longer exist among the entries.
  const categories = board.data?.categories;
  useEffect(() => {
    if (category && categories && !categories.includes(category)) setCategory("");
  }, [category, categories]);

  const allowedStarts = EVENT_START_TYPES[eventKey];
  const onRoster = me.data?.club_id === club.id;
  const columns: DataTableColumn<LeaderboardEntry>[] = [
    { id: "rank", header: t("leaderboard.rank"), cell: (entry) => entry.rank, sortValue: (entry) => entry.rank, width: "4rem", primary: true },
    {
      id: "name",
      header: t("leaderboard.athlete"),
      cell: (entry) => (
        <span className="leaderboard__name">
          {entry.display_name}
          {entry.is_me && <Badge tone="accent">{t("leaderboard.you")}</Badge>}
        </span>
      ),
      sortValue: (entry) => entry.display_name.toLowerCase(),
    },
    { id: "time", header: t("leaderboard.time"), align: "right", cell: (entry) => formatRecordTime(entry.time_ms, fmt), sortValue: (entry) => entry.time_ms },
    {
      id: "category",
      header: t("leaderboard.category"),
      cell: (entry) => (entry.category ? ageCategoryLabel(entry.category, tc) : "—"),
      sortValue: (entry) => entry.category,
      hideOnMobile: true,
    },
    { id: "date", header: t("leaderboard.date"), cell: (entry) => fmt.date(entry.achieved_on, "medium"), sortValue: (entry) => entry.achieved_on, hideOnMobile: true },
  ];

  if (tracks.isSuccess && tracks.data.length === 0) {
    return <EmptyState icon={<Trophy aria-hidden />} title={t("leaderboard.noTracksTitle")} description={t("leaderboard.noTracks")} />;
  }

  return (
    <div className="club-stack">
      <Card title={t("leaderboard.title")} as="section">
        <p className="club-muted">{t("leaderboard.description")}</p>
        <div className="leaderboard__filters">
          <Select
            label={t("leaderboard.event")}
            value={eventKey}
            onChange={(e) => {
              const next = e.target.value as StandardEventKey;
              setEventKey(next);
              if (!EVENT_START_TYPES[next].includes(startType)) setStartType(EVENT_START_TYPES[next][0]);
            }}
          >
            {STANDARD_EVENT_KEYS.map((key) => (
              <option key={key} value={key}>
                {tr(`events.${key}`)}
              </option>
            ))}
          </Select>
          <Select label={t("leaderboard.start")} value={startType} disabled={allowedStarts.length === 1} onChange={(e) => setStartType(e.target.value as "standing" | "flying")}>
            {allowedStarts.map((start) => (
              <option key={start} value={start}>
                {tr(`startTypes.${start}`)}
              </option>
            ))}
          </Select>
          <Select label={t("leaderboard.track")} value={selectedTrackId} onChange={(e) => setTrackId(e.target.value)}>
            {tracks.data?.map((track) => (
              <option key={track.id} value={track.id}>
                {track.name}
              </option>
            ))}
          </Select>
          <Select label={t("leaderboard.sex")} value={sex} onChange={(e) => setSex(e.target.value as LeaderboardQuery["sex"])}>
            <option value="">{t("leaderboard.everyone")}</option>
            <option value="female">{t("leaderboard.women")}</option>
            <option value="male">{t("leaderboard.men")}</option>
          </Select>
          <Select label={t("leaderboard.categoryFilter")} value={category} onChange={(e) => setCategory(e.target.value)} disabled={(categories?.length ?? 0) === 0}>
            <option value="">{t("leaderboard.allCategories")}</option>
            {categories?.map((code) => (
              <option key={code} value={code}>
                {ageCategoryLabel(code, tc)}
              </option>
            ))}
          </Select>
        </div>
      </Card>

      <Card padding="flush" as="section">
        {(tracks.isLoading || board.isLoading) && <SkeletonGroup lines={4} />}
        {board.isError && <p role="alert">{tc("loadError")}</p>}
        {board.data && (
          <DataTable
            caption={t("leaderboard.caption", { event: tr(`events.${eventKey}`), track: board.data.track_name })}
            columns={columns}
            rows={board.data.entries}
            getRowId={(entry) => `${entry.display_name}-${entry.rank}`}
            rowTone={(entry) => (entry.is_me ? "highlight" : undefined)}
            empty={<p className="club-muted leaderboard__empty">{board.data.participants === 0 ? t("leaderboard.nobody") : t("leaderboard.noTimes")}</p>}
          />
        )}
      </Card>
      {board.data && (
        <p className="club-muted">
          {t("leaderboard.participants", { count: board.data.participants })}{" "}
          {onRoster && me.data && !me.data.leaderboard_opt_in && (
            <Link to="/settings/privacy">{t("leaderboard.joinIn")}</Link>
          )}
        </p>
      )}
    </div>
  );
}
