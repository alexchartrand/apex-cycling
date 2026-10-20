import { useState } from "react";
import { MailX, UserPlus } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { errorMessage } from "../api/errors";
import { Button, Card, EmptyState, PageHeader, SkeletonGroup, useToast } from "../components/ui";
import { tokenFromHash } from "../features/clubs/inviteToken";
import { JoinWithLink } from "../features/clubs/JoinWithLink";
import { useAcceptInvite, useInvitePreview } from "../features/clubs/useClubs";
import "../features/clubs/Clubs.css";

/** Where an invitation link lands: say who invites you to what, then join on request. */
export function JoinPage() {
  const { t } = useTranslation("club");
  const navigate = useNavigate();
  const { toast } = useToast();
  // The token lives in the URL fragment, so it never reaches a server log.
  const hash = useLocation().hash;
  const [token] = useState(() => tokenFromHash(hash));
  const preview = useInvitePreview(token);
  const accept = useAcceptInvite();

  async function join() {
    try {
      const club = await accept.mutateAsync(token);
      toast({ title: preview.data?.already_member ? t("joinPage.opened") : t("joinPage.joined", { club: club.name }), tone: "success" });
      navigate(`/club/${club.id}`, { replace: true });
    } catch {
      // shown below
    }
  }

  if (token === "") {
    return (
      <>
        <PageHeader title={t("joinPage.title")} />
        <div className="club-stack">
          <EmptyState compact icon={<MailX aria-hidden />} title={t("joinPage.noLinkTitle")} description={t("joinPage.noLinkDescription")} />
          <JoinWithLink />
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader title={t("joinPage.title")} />
      {preview.isLoading && <SkeletonGroup lines={4} />}
      {preview.isError && (
        <EmptyState
          icon={<MailX aria-hidden />}
          title={t("joinPage.invalidTitle")}
          description={errorMessage(preview.error, { 400: t("joinPage.invalidDescription"), 429: t("joinPage.tooMany") })}
          action={<Link to="/club">{t("page.back")}</Link>}
        />
      )}
      {preview.data && (
        <Card as="section" title={t("joinPage.invitedTo", { club: preview.data.club_name })}>
          <div className="club-form club-form--narrow">
            {preview.data.already_member ? (
              <p>{t("joinPage.alreadyMember", { club: preview.data.club_name })}</p>
            ) : (
              <>
                <p>{t("joinPage.joinAs", { role: t(`roles.${preview.data.role}`).toLowerCase() })}</p>
                <p className="club-muted">{t(`joinPage.consent.${preview.data.role === "coach" ? "coach" : "athlete"}`)}</p>
              </>
            )}
            {accept.isError && <p role="alert">{errorMessage(accept.error, { 409: t("joinPage.conflict"), 400: t("joinPage.invalidDescription") })}</p>}
            <div className="club-form__actions">
              <Button variant="ghost" onClick={() => navigate("/club")}>
                {t("joinPage.notNow")}
              </Button>
              <Button icon={<UserPlus aria-hidden />} onClick={join} loading={accept.isPending}>
                {preview.data.already_member ? t("joinPage.open") : t("joinPage.join")}
              </Button>
            </div>
          </div>
        </Card>
      )}
    </>
  );
}
