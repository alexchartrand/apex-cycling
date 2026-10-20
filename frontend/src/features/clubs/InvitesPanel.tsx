import { useState, type FormEvent } from "react";
import { Copy, Link2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Badge, Button, Card, DataTable, Input, Select, SkeletonGroup, useToast, type DataTableColumn } from "../../components/ui";
import { copyText } from "../../hooks/copyText";
import { useFormat } from "../../i18n/useFormat";
import { useLanguage } from "../../i18n/useLanguage";
import { inviteState } from "./inviteState";
import type { Club, Invite, InviteCreated, InviteRole } from "./types";
import { useCreateInvite, useInvites, useRevokeInvite } from "./useClubs";

const EXPIRY_DAYS = [1, 7, 14, 30, 90] as const;
// "1" = a personal link; null = anyone who opens it, until it expires.
const USE_LIMITS = ["1", "5", "25", "unlimited"] as const;
type UseLimit = (typeof USE_LIMITS)[number];

export function InvitesPanel({ club }: { club: Club }) {
  const { t } = useTranslation("club");
  const { t: tc } = useTranslation("common");
  const fmt = useFormat();
  const { language } = useLanguage();
  const { toast } = useToast();
  const invites = useInvites(club.id, true);
  const create = useCreateInvite(club.id);
  const revoke = useRevokeInvite(club.id);
  const [role, setRole] = useState<InviteRole>("athlete");
  const [days, setDays] = useState<number>(14);
  const [limit, setLimit] = useState<UseLimit>("1");
  const [email, setEmail] = useState("");
  const [created, setCreated] = useState<InviteCreated | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    try {
      const invite = await create.mutateAsync({
        role,
        expires_in_days: days,
        max_uses: limit === "unlimited" ? null : Number(limit),
        email: email.trim() || undefined,
        locale: language,
      });
      setCreated(invite);
      setEmail("");
    } catch {
      // shown below
    }
  }

  async function copy(url: string) {
    toast(
      (await copyText(url))
        ? { title: t("invites.copied"), tone: "success" }
        : { title: t("invites.copyFailed"), description: t("invites.copyFailedHint"), tone: "error" },
    );
  }

  const columns: DataTableColumn<Invite>[] = [
    {
      id: "role",
      header: t("invites.role"),
      primary: true,
      cell: (i) => (
        <span className="club-person">
          <strong>{t(`roles.${i.role}`)}</strong>
          {i.email && <span className="club-person__meta">{i.email}</span>}
        </span>
      ),
    },
    {
      id: "uses",
      header: t("invites.uses"),
      cell: (i) => (i.max_uses === null ? t("invites.usesUnlimited", { count: i.use_count }) : `${i.use_count} / ${i.max_uses}`),
    },
    {
      id: "expires",
      header: t("invites.expires"),
      hideOnMobile: true,
      cell: (i) => fmt.date(i.expires_at.slice(0, 10), "medium"),
    },
    {
      id: "state",
      header: t("invites.status"),
      cell: (i) => {
        const state = inviteState(i);
        return <Badge tone={state === "active" ? "positive" : "neutral"}>{t(`invites.states.${state}`)}</Badge>;
      },
    },
    {
      id: "actions",
      header: <span className="visually-hidden">{t("members.actions")}</span>,
      align: "right",
      cell: (i) => (
        <Button
          size="sm"
          variant="ghost"
          onClick={async () => {
            try {
              await revoke.mutateAsync(i.id);
              toast({ title: t("invites.revoked"), tone: "success" });
            } catch (error) {
              toast({ title: errorMessage(error), tone: "error" });
            }
          }}
        >
          {t("invites.revoke")}
        </Button>
      ),
    },
  ];

  return (
    <div className="club-stack">
      <Card as="section" title={t("invites.newTitle")}>
        <p className="club-muted">{t("invites.newDescription")}</p>
        <form className="club-form" onSubmit={handleSubmit}>
          <div className="club-form__row">
            <Select label={t("invites.joinsAs")} value={role} onChange={(e) => setRole(e.target.value as InviteRole)}>
              <option value="athlete">{t("roles.athlete")}</option>
              <option value="coach">{t("roles.coach")}</option>
            </Select>
            <Select label={t("invites.validFor")} value={days} onChange={(e) => setDays(Number(e.target.value))}>
              {EXPIRY_DAYS.map((d) => (
                <option key={d} value={d}>
                  {t("invites.days", { count: d })}
                </option>
              ))}
            </Select>
            <Select label={t("invites.usableBy")} value={limit} onChange={(e) => setLimit(e.target.value as UseLimit)}>
              {USE_LIMITS.map((l) => (
                <option key={l} value={l}>
                  {l === "unlimited" ? t("invites.anyone") : t("invites.people", { count: Number(l) })}
                </option>
              ))}
            </Select>
          </div>
          <Input
            label={t("invites.email")}
            type="email"
            value={email}
            autoComplete="off"
            hint={t("invites.emailHint")}
            onChange={(e) => setEmail(e.target.value)}
          />
          {create.isError && <p role="alert">{errorMessage(create.error)}</p>}
          <div className="club-form__actions">
            <Button type="submit" icon={<Link2 aria-hidden />} loading={create.isPending}>
              {t("invites.create")}
            </Button>
          </div>
        </form>

        {created && (
          <div className="club-link" role="status">
            <p className="club-link__title">
              {created.emailed ? t("invites.createdEmailed", { email: created.email ?? "" }) : t("invites.created")}
            </p>
            <div className="club-link__row">
              <Input aria-label={t("invites.link")} readOnly value={created.url} onFocus={(e) => e.currentTarget.select()} />
              <Button variant="secondary" icon={<Copy aria-hidden />} onClick={() => copy(created.url)}>
                {tc("copy")}
              </Button>
            </div>
            <p className="club-muted">{t("invites.createdHint")}</p>
          </div>
        )}
      </Card>

      <Card as="section" title={t("invites.listTitle")} padding="flush">
        {invites.isLoading && <SkeletonGroup lines={3} />}
        {invites.isError && <p role="alert">{tc("loadError")}</p>}
        {invites.data && (
          <DataTable
            columns={columns}
            rows={invites.data}
            getRowId={(i) => i.id}
            caption={t("invites.listTitle")}
            empty={<p className="club-muted club-pad">{t("invites.none")}</p>}
          />
        )}
      </Card>
    </div>
  );
}
