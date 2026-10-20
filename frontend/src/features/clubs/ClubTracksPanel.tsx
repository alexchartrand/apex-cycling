import { useState, type FormEvent } from "react";
import { Link2Off, Settings2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Badge, Button, Card, EmptyState, Input, SkeletonGroup, useToast } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { useCurrentUser } from "../auth/useAuth";
import { TrackSettingsDialog } from "../training/TrackSettingsDialog";
import type { TrackSummary } from "../training/types";
import type { Club } from "./types";
import { useClubTracks, useLinkSqorzAccount, useSqorzAccounts, useUnlinkSqorzAccount } from "./useClubs";

/** The tracks of the facilities the club is linked to, editable by its admins. */
export function ClubTracksPanel({ club }: { club: Club }) {
  const { t } = useTranslation("club");
  const fmt = useFormat();
  const { toast } = useToast();
  const isPlatformAdmin = useCurrentUser().data?.is_platform_admin ?? false;
  const accounts = useSqorzAccounts(club.id);
  const tracks = useClubTracks(club.id);
  const link = useLinkSqorzAccount(club.id);
  const unlink = useUnlinkSqorzAccount(club.id);
  const [editing, setEditing] = useState<TrackSummary | null>(null);
  const [accountId, setAccountId] = useState("");

  async function handleLink(e: FormEvent) {
    e.preventDefault();
    try {
      await link.mutateAsync(accountId.trim());
      toast({ title: t("tracks.linked"), tone: "success" });
      setAccountId("");
    } catch {
      // shown below
    }
  }

  const hasAccounts = (accounts.data?.length ?? 0) > 0;

  return (
    <div className="club-stack">
      {(accounts.isLoading || tracks.isLoading) && <SkeletonGroup lines={4} />}
      {accounts.data && !hasAccounts && (
        <EmptyState compact title={t("tracks.noneTitle")} description={isPlatformAdmin ? t("tracks.noneAdmin") : t("tracks.noneDescription")} />
      )}

      {tracks.data?.map((track) => (
        <Card
          key={track.id}
          as="article"
          title={track.name}
          actions={
            track.can_edit && (
              <Button size="sm" variant="secondary" icon={<Settings2 aria-hidden />} onClick={() => setEditing(track)}>
                {t("tracks.edit")}
              </Button>
            )
          }
        >
          <div className="club-facts">
            <Badge tone={track.length_m ? "neutral" : "marker"}>{track.length_m ? fmt.distance(track.length_m) : t("tracks.noLength")}</Badge>
            {track.indoor !== null && <Badge>{track.indoor ? t("tracks.indoor") : t("tracks.outdoor")}</Badge>}
            <Badge>{t("tracks.checkpoints", { count: track.loops.filter((loop) => !loop.hidden).length })}</Badge>
          </div>
        </Card>
      ))}

      {hasAccounts && (
        <Card as="section" title={t("tracks.facilities")}>
          <ul className="club-list">
            {accounts.data?.map((account) => (
              <li key={account.sqorz_account_id} className="club-list__row">
                <span className="club-list__main">
                  {account.track_names.join(", ")}
                  <span className="club-person__meta"> · {t("tracks.account")} {account.sqorz_account_id}</span>
                </span>
                {isPlatformAdmin && (
                  <Button
                    size="sm"
                    variant="ghost"
                    icon={<Link2Off aria-hidden />}
                    onClick={async () => {
                      try {
                        await unlink.mutateAsync(account.sqorz_account_id);
                      } catch (error) {
                        toast({ title: errorMessage(error), tone: "error" });
                      }
                    }}
                  >
                    {t("tracks.unlink")}
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {isPlatformAdmin && (
        <Card as="section" title={t("tracks.linkTitle")}>
          <p className="club-muted">{t("tracks.linkDescription")}</p>
          <form className="club-form club-form--inline" onSubmit={handleLink}>
            <Input label={t("tracks.accountId")} value={accountId} autoComplete="off" onChange={(e) => setAccountId(e.target.value)} />
            <Button type="submit" variant="secondary" disabled={accountId.trim() === ""} loading={link.isPending}>
              {t("tracks.link")}
            </Button>
          </form>
          {link.isError && <p role="alert">{errorMessage(link.error, { 422: t("tracks.unknownAccount") })}</p>}
        </Card>
      )}

      {editing && <TrackSettingsDialog track={editing} open onOpenChange={(open) => !open && setEditing(null)} />}
    </div>
  );
}
