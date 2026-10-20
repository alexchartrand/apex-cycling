import { useState } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Badge, Button, Dialog, IconButton, Select, SkeletonGroup, useToast } from "../../components/ui";
import { X } from "lucide-react";
import { useMyCoaches, useRequestCoachLink, useRevokeCoachLink } from "../coaching/useCoaching";
import type { RosterAthlete } from "./types";
import { useMembers } from "./useClubs";

/** A club admin deciding who coaches a managed athlete: coaches of the club are assigned directly. */
export function ManagedCoachesDialog({
  clubId,
  athlete,
  onClose,
}: {
  clubId: string;
  athlete: RosterAthlete;
  onClose: () => void;
}) {
  const { t } = useTranslation("club");
  const { t: tc } = useTranslation("common");
  const { toast } = useToast();
  const members = useMembers(clubId);
  const coaches = useMyCoaches(athlete.id);
  const request = useRequestCoachLink();
  const revoke = useRevokeCoachLink();
  const [chosen, setChosen] = useState("");

  const linked = new Set((coaches.data ?? []).map((link) => link.coach_user_id));
  const candidates = (members.data ?? []).filter((m) => m.role !== "athlete" && !linked.has(m.user_id));

  async function assign() {
    try {
      await request.mutateAsync({ acting_as: "athlete", athlete_id: athlete.id, coach_user_id: chosen });
      toast({ title: t("roster.coachAssigned"), tone: "success" });
      setChosen("");
    } catch (error) {
      toast({ title: errorMessage(error), tone: "error" });
    }
  }

  async function end(linkId: string) {
    try {
      await revoke.mutateAsync(linkId);
    } catch (error) {
      toast({ title: errorMessage(error), tone: "error" });
    }
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={t("roster.coachesTitle", { name: athlete.display_name })}
      description={t("roster.coachesDescription")}
      footer={<Button onClick={onClose}>{tc("close")}</Button>}
    >
      <div className="club-form">
        {coaches.isLoading && <SkeletonGroup lines={2} />}
        {coaches.data && coaches.data.length === 0 && <p className="club-muted">{t("roster.noCoaches")}</p>}
        <ul className="club-list">
          {coaches.data?.map((link) => (
            <li key={link.id} className="club-list__row">
              <span className="club-list__main">{link.coach_name ?? "—"}</span>
              {link.status !== "active" && <Badge tone="marker">{t("roster.pending")}</Badge>}
              <IconButton aria-label={t("roster.removeCoach", { name: link.coach_name ?? "" })} size="sm" onClick={() => end(link.id)}>
                <X aria-hidden />
              </IconButton>
            </li>
          ))}
        </ul>
        <div className="club-form__row club-form__row--end">
          <Select label={t("roster.addCoach")} value={chosen} onChange={(e) => setChosen(e.target.value)}>
            <option value="">{t("roster.chooseCoach")}</option>
            {candidates.map((m) => (
              <option key={m.user_id} value={m.user_id}>
                {m.display_name ?? m.email}
              </option>
            ))}
          </Select>
          <Button onClick={assign} disabled={chosen === ""} loading={request.isPending}>
            {t("roster.assign")}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
