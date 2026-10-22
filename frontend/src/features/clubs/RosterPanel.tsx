import { useMemo, useState } from "react";
import { Eye, HandHelping, Trash2, UserCog, UserPlus } from "lucide-react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Badge, Button, Card, ConfirmDialog, DataTable, EmptyState, IconButton, Select, SkeletonGroup, Tooltip, useToast, type DataTableColumn } from "../../components/ui";
import { ageCategoryLabel, ageCategoryRank } from "../athletes/ageCategory";
import { useMyAthlete } from "../athletes/useAthlete";
import { useViewAthlete } from "../athletes/useViewAthlete";
import { useCoachedAthletes, useRequestCoachLink } from "../coaching/useCoaching";
import { ManagedAthleteDialog } from "./ManagedAthleteDialog";
import { ManagedCoachesDialog } from "./ManagedCoachesDialog";
import type { Club, RosterAthlete } from "./types";
import { useDeleteManagedAthlete, useRoster } from "./useClubs";

/** The club's athletes: members who joined as athletes, and the managed profiles admins run. */
export function RosterPanel({ club }: { club: Club }) {
  const { t } = useTranslation("club");
  const { t: tc } = useTranslation("common");
  const { toast } = useToast();
  const view = useViewAthlete();
  const me = useMyAthlete().data;
  const roster = useRoster(club.id);
  const coached = useCoachedAthletes();
  const request = useRequestCoachLink();
  const remove = useDeleteManagedAthlete(club.id);
  const [adding, setAdding] = useState(false);
  const [coaching, setCoaching] = useState<RosterAthlete | null>(null);
  const [deleting, setDeleting] = useState<RosterAthlete | null>(null);
  const [asking, setAsking] = useState<string | null>(null);
  const [category, setCategory] = useState("");
  const isAdmin = club.role === "club_admin";

  // Only the categories somebody on the roster is in, youngest first.
  const categories = useMemo(
    () => [...new Set((roster.data ?? []).flatMap((a) => (a.category ? [a.category] : [])))].sort((a, b) => ageCategoryRank(a) - ageCategoryRank(b)),
    [roster.data],
  );
  const shown = useMemo(() => (category ? (roster.data ?? []).filter((a) => a.category === category) : roster.data), [roster.data, category]);

  const linkOf = (athleteId: string) => coached.data?.find((link) => link.athlete_id === athleteId);

  async function ask(athlete: RosterAthlete) {
    setAsking(athlete.id);
    try {
      await request.mutateAsync({ acting_as: "coach", athlete_id: athlete.id });
      toast({ title: t("roster.requestSent", { name: athlete.display_name }), tone: "success" });
    } catch (error) {
      toast({ title: errorMessage(error), tone: "error" });
    } finally {
      setAsking(null);
    }
  }

  const columns: DataTableColumn<RosterAthlete>[] = [
    {
      id: "name",
      header: t("roster.name"),
      primary: true,
      sortValue: (a) => a.display_name.toLowerCase(),
      cell: (a) => (
        <span className="club-person">
          <strong>{a.display_name}</strong>
        </span>
      ),
    },
    {
      id: "category",
      header: t("roster.category"),
      hideOnMobile: true,
      sortValue: (a) => (a.category ? ageCategoryRank(a.category) : Number.MAX_SAFE_INTEGER),
      cell: (a) => (a.category ? ageCategoryLabel(a.category, tc) : "—"),
    },
    {
      id: "kind",
      header: t("roster.kind"),
      hideOnMobile: true,
      cell: (a) => <Badge tone={a.managed ? "marker" : "neutral"}>{a.managed ? t("roster.managed") : t("roster.member")}</Badge>,
    },
    {
      id: "actions",
      header: <span className="visually-hidden">{t("members.actions")}</span>,
      align: "right",
      cell: (a) => {
        const link = linkOf(a.id);
        const canView = a.id === me?.id || link?.status === "active" || isAdmin;
        return (
          <span className="club-actions">
            {canView ? (
              <Button size="sm" variant="secondary" icon={<Eye aria-hidden />} onClick={() => view(a.id)}>
                {t("roster.view")}
              </Button>
            ) : link ? (
              <Badge tone="marker">{t("roster.requested")}</Badge>
            ) : (
              a.id !== me?.id && (
                <Button size="sm" variant="secondary" icon={<HandHelping aria-hidden />} loading={asking === a.id} onClick={() => ask(a)}>
                  {t("roster.ask")}
                </Button>
              )
            )}
            {isAdmin && a.managed && (
              <>
                <Tooltip content={t("roster.coaches")}>
                  <IconButton aria-label={t("roster.coachesOf", { name: a.display_name })} size="sm" onClick={() => setCoaching(a)}>
                    <UserCog aria-hidden />
                  </IconButton>
                </Tooltip>
                <Tooltip content={tc("delete")}>
                  <IconButton aria-label={t("roster.delete", { name: a.display_name })} size="sm" onClick={() => setDeleting(a)}>
                    <Trash2 aria-hidden />
                  </IconButton>
                </Tooltip>
              </>
            )}
          </span>
        );
      },
    },
  ];

  return (
    <Card
      as="section"
      title={t("roster.title")}
      padding="flush"
      actions={
        isAdmin && (
          <Button size="sm" icon={<UserPlus aria-hidden />} onClick={() => setAdding(true)}>
            {t("roster.add")}
          </Button>
        )
      }
    >
      {roster.isLoading && <SkeletonGroup lines={4} />}
      {roster.isError && <p role="alert">{tc("loadError")}</p>}
      {categories.length > 0 && (
        <div className="roster__filters">
          <Select label={t("roster.category")} value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">{t("roster.allCategories")}</option>
            {categories.map((code) => (
              <option key={code} value={code}>
                {ageCategoryLabel(code, tc)}
              </option>
            ))}
          </Select>
        </div>
      )}
      {shown && (
        <DataTable
          columns={columns}
          rows={shown}
          getRowId={(a) => a.id}
          caption={t("roster.title")}
          initialSort={{ columnId: "name", direction: "asc" }}
          empty={<EmptyState compact title={t("roster.empty")} description={isAdmin ? t("roster.emptyAdmin") : undefined} />}
        />
      )}
      <ManagedAthleteDialog clubId={club.id} open={adding} onOpenChange={setAdding} />
      {coaching && <ManagedCoachesDialog clubId={club.id} athlete={coaching} onClose={() => setCoaching(null)} />}
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        tone="danger"
        title={t("roster.deleteTitle", { name: deleting?.display_name ?? "" })}
        description={t("roster.deleteDescription")}
        confirmLabel={tc("delete")}
        cancelLabel={tc("cancel")}
        onConfirm={async () => {
          if (!deleting) return;
          try {
            await remove.mutateAsync(deleting.id);
          } catch (error) {
            toast({ title: errorMessage(error), tone: "error" });
            throw error;
          }
          toast({ title: t("roster.deleted"), tone: "success" });
        }}
      />
    </Card>
  );
}
