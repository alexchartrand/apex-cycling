import { Check, MessageSquare, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Badge, Button, Card, useToast } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { useMyAthlete } from "../athletes/useAthlete";
import { useViewAthlete } from "../athletes/useViewAthlete";
import type { CoachLink } from "./types";
import { useAcceptCoachLink, useCoachInbox, useCommentInbox, useRevokeCoachLink } from "./useCoaching";

/** Link requests to answer and session threads with new comments: what needs the user's attention. */
export function WaitingForYou() {
  const { t } = useTranslation("coach");
  const fmt = useFormat();
  const { toast } = useToast();
  const view = useViewAthlete();
  const me = useMyAthlete().data;
  const requests = useCoachInbox();
  const comments = useCommentInbox();
  const accept = useAcceptCoachLink();
  const decline = useRevokeCoachLink();

  async function answer(link: CoachLink, accepted: boolean) {
    try {
      if (accepted) await accept.mutateAsync(link.id);
      else await decline.mutateAsync(link.id);
      toast({ title: accepted ? t("waiting.accepted") : t("waiting.declined"), tone: "success" });
    } catch (error) {
      toast({ title: errorMessage(error), tone: "error" });
    }
  }

  const requestText = (link: CoachLink) => {
    // An athlete asked me to coach them, or a coach asked to coach an athlete (me, or one I run).
    if (link.status === "pending_coach_acceptance") return t("waiting.askedToCoach", { athlete: link.athlete_name });
    return link.athlete_id === me?.id
      ? t("waiting.wantsToCoachYou", { coach: link.coach_name ?? "—" })
      : t("waiting.wantsToCoach", { coach: link.coach_name ?? "—", athlete: link.athlete_name });
  };

  const requestList = requests.data ?? [];
  const threads = comments.data ?? [];
  if (requestList.length === 0 && threads.length === 0) return null;

  return (
    <Card as="section" title={t("waiting.title")} actions={<Badge tone="accent">{requestList.length + threads.length}</Badge>}>
      <ul className="coach-waiting">
        {requestList.map((link) => (
          <li key={link.id} className="coach-waiting__row">
            <span className="coach-waiting__text">{requestText(link)}</span>
            <span className="coach-waiting__actions">
              <Button size="sm" icon={<Check aria-hidden />} loading={accept.isPending && accept.variables === link.id} onClick={() => answer(link, true)}>
                {t("waiting.accept")}
              </Button>
              <Button size="sm" variant="ghost" icon={<X aria-hidden />} loading={decline.isPending && decline.variables === link.id} onClick={() => answer(link, false)}>
                {t("waiting.decline")}
              </Button>
            </span>
          </li>
        ))}
        {threads.map((item) => (
          <li key={`${item.athlete_id}/${item.external_event_id}`} className="coach-waiting__row">
            <span className="coach-waiting__text">
              <span>
                {/* "Riley · Riley · Session" reads badly when the athlete wrote it themself. */}
                <strong>{item.latest_author_name ?? t("waiting.someone")}</strong>
                {item.latest_author_name !== item.athlete_name && ` · ${item.athlete_name}`} · {item.event_name}
              </span>
              <span className="coach-waiting__excerpt">{item.latest_excerpt}</span>
              <span className="coach-waiting__when">
                {t("waiting.newComments", { count: item.unread_count })} · {fmt.relative(item.latest_at)}
              </span>
            </span>
            <span className="coach-waiting__actions">
              <Button
                size="sm"
                variant="secondary"
                icon={<MessageSquare aria-hidden />}
                onClick={() => view(item.athlete_id, `/sessions/${item.external_event_id}?tab=comments`)}
              >
                {t("waiting.open")}
              </Button>
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
