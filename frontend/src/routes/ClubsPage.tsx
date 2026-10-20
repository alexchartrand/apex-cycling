import { useState } from "react";
import { ChevronRight, Plus, Users } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Badge, Button, Card, EmptyState, PageHeader, SkeletonGroup } from "../components/ui";
import { CreateClubDialog } from "../features/clubs/CreateClubDialog";
import { JoinWithLink } from "../features/clubs/JoinWithLink";
import { useMyClubs } from "../features/clubs/useClubs";
import "../features/clubs/Clubs.css";

export function ClubsPage() {
  const { t } = useTranslation("club");
  const { t: tc } = useTranslation("common");
  const clubs = useMyClubs();
  const [creating, setCreating] = useState(false);

  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description")}
        actions={
          <Button icon={<Plus aria-hidden />} onClick={() => setCreating(true)}>
            {t("create.action")}
          </Button>
        }
      />

      {clubs.isLoading && <SkeletonGroup lines={4} />}
      {clubs.isError && <p role="alert">{tc("loadError")}</p>}

      <div className="club-stack">
        {clubs.data && clubs.data.length === 0 && (
          <EmptyState
            icon={<Users aria-hidden />}
            title={t("empty.title")}
            description={t("empty.description")}
            action={
              <Button icon={<Plus aria-hidden />} onClick={() => setCreating(true)}>
                {t("create.action")}
              </Button>
            }
          />
        )}

        {clubs.data && clubs.data.length > 0 && (
          <div className="club-grid">
            {clubs.data.map((club) => (
              <Link key={club.id} to={`/club/${club.id}`} className="club-card">
                <div className="club-card__body">
                  <strong className="club-card__name">{club.name}</strong>
                  <span className="club-person__meta">{club.timezone}</span>
                </div>
                <Badge tone={club.role === "club_admin" ? "accent" : "neutral"}>{t(`roles.${club.role}`)}</Badge>
                <ChevronRight aria-hidden className="club-card__chevron" />
              </Link>
            ))}
          </div>
        )}

        {clubs.data && <JoinWithLink />}
        {clubs.data && clubs.data.length > 0 && (
          <Card as="section" title={t("create.anotherTitle")}>
            <p className="club-muted">{t("create.anotherDescription")}</p>
          </Card>
        )}
      </div>

      <CreateClubDialog open={creating} onOpenChange={setCreating} />
    </>
  );
}
