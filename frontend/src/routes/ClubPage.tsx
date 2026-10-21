import { SearchX } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { EmptyState, PageHeader, SkeletonGroup, TabPanel, Tabs, type TabItem } from "../components/ui";
import { ClubSettingsPanel } from "../features/clubs/ClubSettingsPanel";
import { ClubTracksPanel } from "../features/clubs/ClubTracksPanel";
import { LeaderboardPanel } from "../features/clubs/LeaderboardPanel";
import { InvitesPanel } from "../features/clubs/InvitesPanel";
import { MembersPanel } from "../features/clubs/MembersPanel";
import { RosterPanel } from "../features/clubs/RosterPanel";
import { sectionsFor, type ClubSection } from "../features/clubs/sections";
import { useMyClubs } from "../features/clubs/useClubs";
import "../features/clubs/Clubs.css";

export function ClubPage() {
  const { t } = useTranslation("club");
  const { t: tc } = useTranslation("common");
  const navigate = useNavigate();
  const params = useParams();
  const clubId = params.clubId ?? "";
  const section = params["*"] ?? "";
  const clubs = useMyClubs();
  const club = clubs.data?.find((candidate) => candidate.id === clubId);

  if (clubs.isLoading) return <SkeletonGroup lines={6} />;
  if (clubs.isError) return <p role="alert">{tc("loadError")}</p>;
  if (!club) {
    return (
      <EmptyState
        icon={<SearchX aria-hidden />}
        title={t("page.notFound")}
        action={<Link to="/club">{t("page.back")}</Link>}
      />
    );
  }

  const allowed = sectionsFor(club.role);
  if (!allowed.includes(section as ClubSection)) return <Navigate to={`/club/${club.id}/members`} replace />;
  const current = section as ClubSection;

  const items: TabItem<ClubSection>[] = allowed.map((value) => ({ value, label: t(`tabs.${value}`) }));

  return (
    <>
      <PageHeader back={{ to: "/club", label: t("page.back") }} eyebrow={t(`roles.${club.role}`)} title={club.name} />
      <Tabs items={items} value={current} onValueChange={(next) => navigate(`/club/${club.id}/${next}`)} aria-label={t("page.tabsLabel")}>
        <TabPanel value="members">
          <MembersPanel club={club} />
        </TabPanel>
        <TabPanel value="athletes">
          <RosterPanel club={club} />
        </TabPanel>
        <TabPanel value="leaderboard">
          <LeaderboardPanel club={club} />
        </TabPanel>
        <TabPanel value="invites">
          <InvitesPanel club={club} />
        </TabPanel>
        <TabPanel value="tracks">
          <ClubTracksPanel club={club} />
        </TabPanel>
        <TabPanel value="settings">
          <ClubSettingsPanel club={club} />
        </TabPanel>
      </Tabs>
    </>
  );
}
