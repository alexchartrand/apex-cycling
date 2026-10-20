import { useState } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Badge, Button, Card, ConfirmDialog, EmptyState, Select, SkeletonGroup, useToast } from "../../components/ui";
import { useCurrentUser } from "../auth/useAuth";
import { useMemberLists, useMyClubs } from "../clubs/useClubs";
import { AskByEmail } from "./AskByEmail";
import type { CoachLink } from "./types";
import { useAcceptCoachLink, useMyCoaches, useRequestCoachLink, useRevokeCoachLink } from "./useCoaching";

/** The people who coach me (and requests either way), and asking someone new. */
export function MyCoaches() {
  const { t } = useTranslation("coach");
  const { t: tc } = useTranslation("common");
  const { toast } = useToast();
  const me = useCurrentUser().data;
  const coaches = useMyCoaches();
  const clubs = useMyClubs();
  const members = useMemberLists((clubs.data ?? []).map((club) => club.id));
  const request = useRequestCoachLink();
  const accept = useAcceptCoachLink();
  const revoke = useRevokeCoachLink();
  const [ending, setEnding] = useState<CoachLink | null>(null);
  const [chosen, setChosen] = useState("");

  const linked = new Set((coaches.data ?? []).map((link) => link.coach_user_id));
  // Coaches and admins of my clubs, each once, that I haven't already linked.
  const candidates = new Map<string, string>();
  members.forEach((query, index) => {
    for (const m of query.data ?? []) {
      if (m.role !== "athlete" && m.user_id !== me?.id && !linked.has(m.user_id) && !candidates.has(m.user_id)) {
        candidates.set(m.user_id, `${m.display_name ?? m.email ?? "—"} · ${clubs.data?.[index]?.name ?? ""}`);
      }
    }
  });

  async function ask(payload: Parameters<typeof request.mutateAsync>[0], done: string) {
    try {
      await request.mutateAsync(payload);
      toast({ title: done, tone: "success" });
    } catch (error) {
      toast({ title: errorMessage(error), tone: "error" });
    }
  }

  const statusBadge = (link: CoachLink) =>
    link.status === "active" ? (
      <Badge tone="positive">{t("coaches.active")}</Badge>
    ) : link.needs_my_response ? (
      <Badge tone="accent">{t("coaches.needsAnswer")}</Badge>
    ) : (
      <Badge tone="marker">{t("coaches.waiting")}</Badge>
    );

  return (
    <div className="coach-stack">
      <Card as="section" title={t("coaches.title")}>
        {coaches.isLoading && <SkeletonGroup lines={2} />}
        {coaches.isError && <p role="alert">{tc("loadError")}</p>}
        {coaches.data && coaches.data.length === 0 && (
          <EmptyState compact title={t("coaches.emptyTitle")} description={t("coaches.emptyDescription")} />
        )}
        <ul className="coach-waiting">
          {coaches.data?.map((link) => (
            <li key={link.id} className="coach-waiting__row">
              <span className="coach-waiting__text">{link.coach_name ?? "—"}</span>
              {statusBadge(link)}
              <span className="coach-waiting__actions">
                {link.needs_my_response && (
                  <Button
                    size="sm"
                    loading={accept.isPending && accept.variables === link.id}
                    onClick={async () => {
                      try {
                        await accept.mutateAsync(link.id);
                      } catch (error) {
                        toast({ title: errorMessage(error), tone: "error" });
                      }
                    }}
                  >
                    {t("waiting.accept")}
                  </Button>
                )}
                <Button size="sm" variant="ghost" onClick={() => setEnding(link)}>
                  {link.status === "active" ? t("coaches.end") : link.needs_my_response ? t("waiting.decline") : t("cards.cancel")}
                </Button>
              </span>
            </li>
          ))}
        </ul>
      </Card>

      <Card as="section" title={t("coaches.askTitle")}>
        <div className="coach-stack">
          <p className="coach-muted">{t("coaches.askDescription")}</p>
          {candidates.size > 0 && (
            <div className="coach-ask">
              <Select label={t("coaches.fromClub")} value={chosen} onChange={(e) => setChosen(e.target.value)}>
                <option value="">{t("coaches.choose")}</option>
                {[...candidates].map(([userId, label]) => (
                  <option key={userId} value={userId}>
                    {label}
                  </option>
                ))}
              </Select>
              <Button
                variant="secondary"
                disabled={chosen === ""}
                loading={request.isPending && request.variables !== undefined && "coach_user_id" in request.variables}
                onClick={async () => {
                  await ask({ acting_as: "athlete", coach_user_id: chosen }, t("coaches.requested"));
                  setChosen("");
                }}
              >
                {t("coaches.ask")}
              </Button>
            </div>
          )}
          <AskByEmail
            label={t("coaches.byEmail")}
            action={t("coaches.ask")}
            pending={request.isPending && request.variables !== undefined && "coach_email" in request.variables}
            onSubmit={(email) => ask({ acting_as: "athlete", coach_email: email }, t("coaches.emailRequested"))}
          />
        </div>
      </Card>

      <ConfirmDialog
        open={ending !== null}
        onOpenChange={(open) => !open && setEnding(null)}
        tone="danger"
        title={t("coaches.endTitle", { name: ending?.coach_name ?? "" })}
        description={ending?.status === "active" ? t("coaches.endDescription") : undefined}
        confirmLabel={tc("confirm")}
        cancelLabel={tc("cancel")}
        onConfirm={async () => {
          if (!ending) return;
          try {
            await revoke.mutateAsync(ending.id);
          } catch (error) {
            toast({ title: errorMessage(error), tone: "error" });
            throw error;
          }
        }}
      />
    </div>
  );
}
