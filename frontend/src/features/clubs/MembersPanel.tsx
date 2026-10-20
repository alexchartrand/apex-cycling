import { useState } from "react";
import { LogOut, UserMinus } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { errorMessage } from "../../api/errors";
import { Badge, Card, ConfirmDialog, DataTable, IconButton, Select, SkeletonGroup, useToast, type DataTableColumn } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { useCurrentUser } from "../auth/useAuth";
import type { Club, ClubRole, Member } from "./types";
import { useMembers, useRemoveMember, useSetMemberRole } from "./useClubs";

const ROLES: ClubRole[] = ["athlete", "coach", "club_admin"];

export function MembersPanel({ club }: { club: Club }) {
  const { t } = useTranslation("club");
  const { t: tc } = useTranslation("common");
  const fmt = useFormat();
  const navigate = useNavigate();
  const { toast } = useToast();
  const me = useCurrentUser().data;
  const members = useMembers(club.id);
  const setRole = useSetMemberRole(club.id);
  const remove = useRemoveMember(club.id);
  const [leaving, setLeaving] = useState<Member | null>(null);
  const isAdmin = club.role === "club_admin";
  // Errors the backend words in English get a translated message for the cases a member can hit.
  const failure = (error: unknown) => errorMessage(error, { 409: t("members.lastAdmin") });

  async function changeRole(member: Member, role: ClubRole) {
    try {
      await setRole.mutateAsync({ membershipId: member.id, role });
      toast({ title: t("members.roleChanged"), tone: "success" });
    } catch (error) {
      toast({ title: failure(error), tone: "error" });
    }
  }

  async function confirmRemove() {
    if (!leaving) return;
    const wasMe = leaving.user_id === me?.id;
    try {
      await remove.mutateAsync(leaving.id);
    } catch (error) {
      toast({ title: failure(error), tone: "error" });
      throw error; // keeps the dialog open
    }
    toast({ title: wasMe ? t("members.left") : t("members.removed"), tone: "success" });
    if (wasMe) navigate("/club");
  }

  const columns: DataTableColumn<Member>[] = [
    {
      id: "name",
      header: t("members.name"),
      primary: true,
      sortValue: (m) => (m.display_name ?? "").toLowerCase(),
      cell: (m) => (
        <span className="club-person">
          <strong>{m.display_name ?? "—"}</strong>
          {m.email && <span className="club-person__meta">{m.email}</span>}
        </span>
      ),
    },
    {
      id: "role",
      header: t("members.role"),
      cell: (m) =>
        isAdmin ? (
          <Select
            scale="sm"
            aria-label={t("members.roleOf", { name: m.display_name ?? "" })}
            value={m.role}
            onChange={(e) => changeRole(m, e.target.value as ClubRole)}
          >
            {ROLES.map((role) => (
              <option key={role} value={role}>
                {t(`roles.${role}`)}
              </option>
            ))}
          </Select>
        ) : (
          <Badge tone={m.role === "club_admin" ? "accent" : "neutral"}>{t(`roles.${m.role}`)}</Badge>
        ),
    },
    {
      id: "joined",
      header: t("members.joined"),
      hideOnMobile: true,
      sortValue: (m) => m.joined_at,
      cell: (m) => fmt.date(m.joined_at.slice(0, 10), "medium"),
    },
    {
      id: "actions",
      header: <span className="visually-hidden">{t("members.actions")}</span>,
      align: "right",
      cell: (m) => {
        const mine = m.user_id === me?.id;
        if (!mine && !isAdmin) return null;
        const label = mine ? t("members.leave") : t("members.remove", { name: m.display_name ?? "" });
        return (
          <IconButton aria-label={label} size="sm" onClick={() => setLeaving(m)}>
            {mine ? <LogOut aria-hidden /> : <UserMinus aria-hidden />}
          </IconButton>
        );
      },
    },
  ];

  return (
    <Card as="section" title={t("members.title")} padding="flush">
      {members.isLoading && <SkeletonGroup lines={4} />}
      {members.isError && <p role="alert">{tc("loadError")}</p>}
      {members.data && (
        <DataTable columns={columns} rows={members.data} getRowId={(m) => m.id} caption={t("members.title")} initialSort={{ columnId: "name", direction: "asc" }} />
      )}
      <ConfirmDialog
        open={leaving !== null}
        onOpenChange={(open) => !open && setLeaving(null)}
        tone="danger"
        title={leaving?.user_id === me?.id ? t("members.leaveTitle", { club: club.name }) : t("members.removeTitle", { name: leaving?.display_name ?? "" })}
        description={leaving?.user_id === me?.id ? t("members.leaveDescription") : t("members.removeDescription")}
        confirmLabel={leaving?.user_id === me?.id ? t("members.leave") : t("members.removeConfirm")}
        cancelLabel={tc("cancel")}
        onConfirm={confirmRemove}
      />
    </Card>
  );
}
