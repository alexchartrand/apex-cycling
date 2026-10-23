import { useMemo } from "react";
import { ChevronLeft, ChevronRight, SearchX } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { ButtonLink, EmptyState, PageHeader, SegmentedControl, SkeletonGroup, TabPanel, Tabs, Tooltip, type TabItem } from "../components/ui";
import { RecordingActions } from "../features/activities/RecordingActions";
import { RecordingStreams, RecordingView } from "../features/activities/RecordingView";
import { effortBands, lapSpeeds, recordingClockStart, sessionGearing, type SessionOverlay } from "../features/activities/sessionOverlay";
import { useActivity } from "../features/activities/useActivities";
import { useActiveAthlete, useViewingOther } from "../features/athletes/useActiveAthlete";
import { CommentsTab } from "../features/comments/CommentsTab";
import { GearPicker } from "../features/equipment/GearPicker";
import { useBikes, useSessionGear } from "../features/equipment/useEquipment";
import { useComments } from "../features/comments/useComments";
import { SessionInsights } from "../features/insights/SessionInsights";
import { useSessionInsights } from "../features/insights/useInsights";
import { useRecords } from "../features/records/useRecords";
import { EffortCard } from "../features/training/session/EffortCard";
import { NotesTab } from "../features/training/session/NotesTab";
import { TrackLaps } from "../features/training/session/TrackLaps";
import { TrackOverview } from "../features/training/session/TrackOverview";
import { useSessionDetail, useSessionEfforts, useSessions, useTracks } from "../features/training/useTraining";
import { useFormat } from "../i18n/useFormat";
import "./SessionDetailPage.css";

const TABS = ["overview", "laps", "efforts", "ride", "notes", "comments"] as const;
type SessionTab = (typeof TABS)[number];

const isTab = (value: string | null): value is SessionTab => TABS.includes(value as SessionTab);

export function SessionDetailPage() {
  const { t } = useTranslation("training");
  const { t: tg } = useTranslation("equipment");
  const fmt = useFormat();
  const { eventId = "" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedTab = searchParams.get("tab");

  const athleteId = useActiveAthlete().data?.id ?? "";
  const { viewing } = useViewingOther();
  // A coach reads a recording; the athlete (or a club admin for a managed athlete) edits it.
  const canEditRecording = !viewing || viewing.user_id === null;
  const detail = useSessionDetail(athleteId, eventId);
  const sessions = useSessions(athleteId);
  const tracks = useTracks(athleteId);
  const efforts = useSessionEfforts(athleteId, eventId);
  const records = useRecords(athleteId);
  const insights = useSessionInsights(athleteId, eventId);
  const comments = useComments(athleteId, eventId);
  const bikes = useBikes(athleteId);
  const sessionGear = useSessionGear(athleteId, eventId);

  // Sessions are listed newest first: "previous" is the older one.
  const index = sessions.data?.findIndex((s) => s.external_event_id === eventId) ?? -1;
  const older = index >= 0 ? sessions.data?.[index + 1] : undefined;
  const newer = index > 0 ? sessions.data?.[index - 1] : undefined;
  const summary = index >= 0 ? sessions.data?.[index] : undefined;

  const notFound = detail.error instanceof ApiError && detail.error.status === 404;
  const session = detail.data;

  // The Ride tab: the recordings linked to this session (head unit, power meter), one at a time.
  const recordings = session?.activities ?? [];
  const recording = recordings.find((r) => r.id === searchParams.get("recording")) ?? recordings[0];
  const recordingActivity = useActivity(athleteId, recording?.id ?? "");
  const overlay = useMemo((): SessionOverlay | undefined => {
    if (!session || !recording) return undefined;
    const lengths = new Map((tracks.data ?? []).flatMap((track) => (track.length_m ? [[track.id, track.length_m] as const] : [])));
    return {
      clockStartMs: recordingClockStart(recording),
      bands: effortBands(efforts.data ?? [], recording),
      laps: lapSpeeds(session.tracks, lengths, recording),
      gearing: sessionGearing(session.gear_setup_id, efforts.data ?? [], bikes.data ?? [], recording),
    };
  }, [session, recording, tracks.data, efforts.data, bikes.data]);

  const tab: SessionTab =
    !isTab(requestedTab) || (requestedTab === "ride" && session && recordings.length === 0) ? "overview" : requestedTab;

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
    ...(recordings.length > 0 ? [{ value: "ride" as const, label: t("session.tabs.ride") }] : []),
    { value: "notes", label: t("session.tabs.notes") },
    { value: "comments", label: t("session.tabs.comments"), count: comments.data?.length || undefined },
  ];

  // The chosen recording follows from tab to tab (Overview shows its streams, Ride the rest).
  function selectTab(next: SessionTab) {
    const chosen = searchParams.get("recording");
    setSearchParams({ ...(next === "overview" ? {} : { tab: next }), ...(chosen ? { recording: chosen } : {}) }, { replace: true });
  }

  const recordingPicker = recordings.length > 1 && recording && (
    <SegmentedControl
      size="sm"
      aria-label={t("session.recording")}
      value={recording.id}
      onChange={(id) => setSearchParams({ ...(tab === "overview" ? {} : { tab }), recording: id }, { replace: true })}
      options={recordings.map((r) => ({ value: r.id, label: r.name ?? fmt.time(r.start_time) }))}
    />
  );

  const rideHref = (id: string) => `/sessions/${encodeURIComponent(eventId)}?tab=ride&recording=${encodeURIComponent(id)}`;

  return (
    <>
      <PageHeader
        back={{ to: "/log", label: t("session.back") }}
        eyebrow={session ? `${fmt.date(session.event_date, "long")}${summary ? ` · ${summary.track_names.join(", ")}` : ""}` : undefined}
        title={session?.event_name ?? summary?.event_name ?? " "}
        actions={
          <>
            {tab === "ride" && recordingActivity.data && (
              <RecordingActions
                athleteId={athleteId}
                activity={recordingActivity.data}
                canEdit={canEditRecording}
                onDeleted={() => setSearchParams({ tab: "ride" }, { replace: true })}
              />
            )}
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
            <Link key={recording.id} to={rideHref(recording.id)} className="session-detail__recording">
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

      {session && bikes.data && (
        <div className="session-detail__gear">
          <GearPicker
            bikes={bikes.data}
            value={session.gear_setup_id ?? null}
            onChange={sessionGear.mutateAsync}
            label={tg("picker.session")}
            emptyLabel={tg("picker.none")}
            pending={sessionGear.isPending}
            error={sessionGear.error}
          />
        </div>
      )}

      {session && <SessionInsights athleteId={athleteId} eventId={eventId} />}

      {session && (
        <Tabs items={items} value={tab} onValueChange={selectTab} aria-label={t("session.tabs.label")}>
          <TabPanel value="overview">
            <div className="session-detail">
              {session.tracks.map((track) => (
                <TrackOverview
                  key={track.track_id}
                  track={track}
                  meta={tracks.data?.find((candidate) => candidate.id === track.track_id)}
                  insights={insights.data}
                  records={(records.data ?? []).filter(
                    (record) => record.source === "sqorz" && record.external_event_id === eventId && record.track_id === track.track_id,
                  )}
                />
              ))}
              {recording && (
                <>
                  {recordingPicker}
                  <RecordingStreams key={recording.id} athleteId={athleteId} activityId={recording.id} session={overlay} />
                </>
              )}
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
                <EffortCard
                  key={effort.lap_ids[0]}
                  athleteId={athleteId}
                  eventId={eventId}
                  effort={effort}
                  bikes={bikes.data ?? []}
                  date={session.event_date}
                  trackLengthM={tracks.data?.find((candidate) => candidate.id === effort.track_id)?.length_m ?? null}
                />
              ))}
            </div>
          </TabPanel>

          <TabPanel value="ride">
            <div className="session-detail">
              {recordingPicker}
              {recordingActivity.isLoading && <SkeletonGroup lines={6} />}
              {recordingActivity.isError && <p role="alert">{t("session.loadError")}</p>}
              {recordingActivity.data && (
                <RecordingView key={recordingActivity.data.id} athleteId={athleteId} activity={recordingActivity.data} canEdit={canEditRecording} streams={false} />
              )}
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
