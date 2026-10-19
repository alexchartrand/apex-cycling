import { ChevronLeft, ChevronRight, SearchX } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { ButtonLink, EmptyState, PageHeader, SkeletonGroup, Tooltip } from "../components/ui";
import { useActiveAthlete } from "../features/athletes/useActiveAthlete";
import { SessionTrackCard } from "../features/training/SessionTrackCard";
import { useSessionDetail, useSessions, useTracks } from "../features/training/useTraining";
import { useFormat } from "../i18n/useFormat";
import "./SessionDetailPage.css";

export function SessionDetailPage() {
  const { t } = useTranslation("training");
  const fmt = useFormat();
  const { eventId = "" } = useParams();
  const athleteId = useActiveAthlete().data?.id ?? "";
  const detail = useSessionDetail(athleteId, eventId);
  const sessions = useSessions(athleteId);
  const tracks = useTracks(athleteId);

  // Sessions are listed newest first: "previous" is the older one.
  const index = sessions.data?.findIndex((s) => s.external_event_id === eventId) ?? -1;
  const older = index >= 0 ? sessions.data?.[index + 1] : undefined;
  const newer = index > 0 ? sessions.data?.[index - 1] : undefined;
  const summary = index >= 0 ? sessions.data?.[index] : undefined;

  const notFound = detail.error instanceof ApiError && detail.error.status === 404;

  const navButton = (target: typeof older, label: string, icon: React.ReactNode) =>
    target ? (
      <Tooltip content={label}>
        <ButtonLink to={`/sessions/${target.external_event_id}`} variant="secondary" className="btn--icon" aria-label={label}>
          {icon}
        </ButtonLink>
      </Tooltip>
    ) : null;

  return (
    <>
      <PageHeader
        back={{ to: "/log", label: t("session.back") }}
        eyebrow={detail.data ? `${fmt.date(detail.data.event_date, "long")}${summary ? ` · ${summary.track_names.join(", ")}` : ""}` : undefined}
        title={detail.data?.event_name ?? summary?.event_name ?? " "}
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

      <div className="session-detail">
        {detail.data?.tracks.map((track) => {
          const meta = tracks.data?.find((candidate) => candidate.id === track.track_id);
          return <SessionTrackCard key={track.track_id} track={track} loops={meta?.loops ?? []} lengthM={meta?.length_m} />;
        })}
      </div>
    </>
  );
}
