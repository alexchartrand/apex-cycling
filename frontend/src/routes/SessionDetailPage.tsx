import { ChevronLeft, ChevronRight, SearchX } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { ButtonLink, EmptyState, PageHeader, SkeletonGroup, TabPanel, Tabs, Tooltip, type TabItem } from "../components/ui";
import { useActiveAthlete } from "../features/athletes/useActiveAthlete";
import { CommentsTab } from "../features/comments/CommentsTab";
import { useComments } from "../features/comments/useComments";
import { useRecords } from "../features/records/useRecords";
import { EffortCard } from "../features/training/session/EffortCard";
import { NotesTab } from "../features/training/session/NotesTab";
import { TrackLaps } from "../features/training/session/TrackLaps";
import { TrackOverview } from "../features/training/session/TrackOverview";
import { useSessionDetail, useSessionEfforts, useSessions, useTracks } from "../features/training/useTraining";
import { useFormat } from "../i18n/useFormat";
import "./SessionDetailPage.css";

const TABS = ["overview", "laps", "efforts", "notes", "comments"] as const;
type SessionTab = (typeof TABS)[number];

const isTab = (value: string | null): value is SessionTab => TABS.includes(value as SessionTab);

export function SessionDetailPage() {
  const { t } = useTranslation("training");
  const fmt = useFormat();
  const { eventId = "" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedTab = searchParams.get("tab");
  const tab: SessionTab = isTab(requestedTab) ? requestedTab : "overview";

  const athleteId = useActiveAthlete().data?.id ?? "";
  const detail = useSessionDetail(athleteId, eventId);
  const sessions = useSessions(athleteId);
  const tracks = useTracks(athleteId);
  const efforts = useSessionEfforts(athleteId, eventId);
  const records = useRecords(athleteId);
  const comments = useComments(athleteId, eventId);

  // Sessions are listed newest first: "previous" is the older one.
  const index = sessions.data?.findIndex((s) => s.external_event_id === eventId) ?? -1;
  const older = index >= 0 ? sessions.data?.[index + 1] : undefined;
  const newer = index > 0 ? sessions.data?.[index - 1] : undefined;
  const summary = index >= 0 ? sessions.data?.[index] : undefined;

  const notFound = detail.error instanceof ApiError && detail.error.status === 404;
  const session = detail.data;

  const navButton = (target: typeof older, label: string, icon: React.ReactNode) =>
    target ? (
      <Tooltip content={label}>
        <ButtonLink to={`/sessions/${target.external_event_id}${tab === "overview" ? "" : `?tab=${tab}`}`} variant="secondary" className="btn--icon" aria-label={label}>
          {icon}
        </ButtonLink>
      </Tooltip>
    ) : null;

  const items: TabItem<SessionTab>[] = [
    { value: "overview", label: t("session.tabs.overview") },
    { value: "laps", label: t("session.tabs.laps"), count: session?.tracks.reduce((sum, track) => sum + track.laps.length, 0) },
    { value: "efforts", label: t("session.tabs.efforts"), count: efforts.data?.length },
    { value: "notes", label: t("session.tabs.notes") },
    { value: "comments", label: t("session.tabs.comments"), count: comments.data?.length || undefined },
  ];

  function selectTab(next: SessionTab) {
    setSearchParams(next === "overview" ? {} : { tab: next }, { replace: true });
  }

  return (
    <>
      <PageHeader
        back={{ to: "/log", label: t("session.back") }}
        eyebrow={session ? `${fmt.date(session.event_date, "long")}${summary ? ` · ${summary.track_names.join(", ")}` : ""}` : undefined}
        title={session?.event_name ?? summary?.event_name ?? " "}
        actions={
          <>
            {navButton(older, t("session.previous"), <ChevronLeft aria-hidden />)}
            {navButton(newer, t("session.next"), <ChevronRight aria-hidden />)}
          </>
        }
      />

      {detail.isLoading && <SkeletonGroup lines={8} />}
      {notFound && <EmptyState icon={<SearchX aria-hidden />} title={t("session.notFound")} />}
      {detail.isError && !notFound && <p role="alert">{t("session.loadError")}</p>}

      {session && session.activities && session.activities.length > 0 && (
        <p className="session-detail__recordings">
          <span>{t("session.recordings")}</span>
          {session.activities.map((recording) => (
            <Link key={recording.id} to={`/activities/${recording.id}`} className="session-detail__recording">
              {recording.name ?? fmt.time(recording.start_time)}
            </Link>
          ))}
          {session.activities.some((recording) => recording.has_power) && (
            <Link to={`/aero?session=${encodeURIComponent(session.external_event_id)}`} className="session-detail__recording">
              {t("session.estimateCda")}
            </Link>
          )}
        </p>
      )}

      {session && (
        <Tabs items={items} value={tab} onValueChange={selectTab} aria-label={t("session.tabs.label")}>
          <TabPanel value="overview">
            <div className="session-detail">
              {session.tracks.map((track) => (
                <TrackOverview
                  key={track.track_id}
                  track={track}
                  meta={tracks.data?.find((candidate) => candidate.id === track.track_id)}
                  records={(records.data ?? []).filter(
                    (record) => record.source === "sqorz" && record.external_event_id === eventId && record.track_id === track.track_id,
                  )}
                />
              ))}
            </div>
          </TabPanel>

          <TabPanel value="laps">
            <div className="session-detail">
              {session.tracks.map((track) => (
                <TrackLaps
                  key={track.track_id}
                  athleteId={athleteId}
                  sessionTitle={session.event_name}
                  track={track}
                  meta={tracks.data?.find((candidate) => candidate.id === track.track_id)}
                />
              ))}
            </div>
          </TabPanel>

          <TabPanel value="efforts">
            <div className="session-detail">
              {efforts.isLoading && <SkeletonGroup lines={4} />}
              {efforts.isError && <p role="alert">{t("session.loadError")}</p>}
              {efforts.data && efforts.data.length === 0 && <EmptyState compact icon={<SearchX aria-hidden />} title={t("efforts.empty")} />}
              {efforts.data && efforts.data.length > 0 && <p className="session-detail__note">{t("efforts.description")}</p>}
              {efforts.data?.map((effort) => (
                <EffortCard key={effort.lap_ids[0]} athleteId={athleteId} eventId={eventId} effort={effort} />
              ))}
            </div>
          </TabPanel>

          <TabPanel value="notes">
            {/* Re-keyed on the session so an edit made elsewhere (or on another session) never shows stale fields. */}
            <NotesTab key={session.external_event_id} athleteId={athleteId} session={session} />
          </TabPanel>

          <TabPanel value="comments">
            <CommentsTab key={session.external_event_id} athleteId={athleteId} eventId={eventId} />
          </TabPanel>
        </Tabs>
      )}
    </>
  );
}
