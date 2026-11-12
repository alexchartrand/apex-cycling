import { useState } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Badge, Card, Checkbox, DataTable, EmptyState, Input, SkeletonGroup, StatTile, type DataTableColumn } from "../../components/ui";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import { useFormat } from "../../i18n/useFormat";
import type { AdminAiRow } from "./types";
import { useAdminAi, useUpdateAdminAi } from "./useAiCoach";

function CapInput({ row, fallback }: { row: AdminAiRow; fallback: number }) {
  const { t } = useTranslation("aicoach");
  const update = useUpdateAdminAi();
  const [value, setValue] = useState(row.monthly_token_cap ? String(row.monthly_token_cap) : "");
  const commit = () => {
    const cap = value.trim() === "" ? 0 : Math.max(0, Math.round(Number(value)));
    if (Number.isNaN(cap) || cap === (row.monthly_token_cap ?? 0)) return;
    update.mutate({ athleteId: row.athlete_id, monthly_token_cap: cap });
  };
  return (
    <Input
      aria-label={t("admin.cap")}
      inputMode="numeric"
      placeholder={String(fallback)}
      value={value}
      onChange={(event) => setValue(event.target.value)}
      onBlur={commit}
      onKeyDown={(event) => event.key === "Enter" && commit()}
      error={update.isError ? errorMessage(update.error) : undefined}
    />
  );
}

/** Platform admin: who may use the AI coach, their monthly cap and what they used. */
export function AiCoachAdmin() {
  const { t } = useTranslation("aicoach");
  const fmt = useFormat();
  const [search, setSearch] = useState("");
  const q = useDebouncedValue(search, 300);
  const overview = useAdminAi(q);
  const update = useUpdateAdminAi();

  const columns: DataTableColumn<AdminAiRow>[] = [
    {
      id: "athlete",
      header: t("admin.athlete"),
      primary: true,
      cell: (row) => (
        <>
          {row.display_name}
          <br />
          <span className="ai-muted">{row.email}</span>
        </>
      ),
    },
    {
      id: "enabled",
      header: t("admin.enabled"),
      cell: (row) => (
        <Checkbox
          label={row.enabled ? t("admin.on") : t("admin.off")}
          checked={row.enabled}
          disabled={update.isPending}
          onChange={(event) => update.mutate({ athleteId: row.athlete_id, enabled: event.target.checked })}
        />
      ),
    },
    {
      id: "consent",
      header: t("admin.consent"),
      cell: (row) => (row.consented ? <Badge tone="positive">{t("admin.consented")}</Badge> : <Badge>{t("admin.notYet")}</Badge>),
    },
    {
      id: "cap",
      header: t("admin.cap"),
      cell: (row) => <CapInput key={`${row.athlete_id}-${row.monthly_token_cap}`} row={row} fallback={overview.data?.default_monthly_tokens ?? 0} />,
    },
    {
      id: "usage",
      header: t("admin.usage"),
      cell: (row) => (
        <>
          {fmt.number(row.month_tokens, 0)}
          <br />
          <span className="ai-muted">{t("admin.cost", { value: fmt.number(row.month_cost_usd, 2, 2) })}</span>
        </>
      ),
    },
  ];

  return (
    <Card as="section" title={t("admin.title")}>
      {overview.isLoading ? (
        <SkeletonGroup lines={4} />
      ) : overview.isError || !overview.data ? (
        <EmptyState title={t("admin.loadFailed")} description={errorMessage(overview.error)} />
      ) : (
        <div className="ai-stack">
          {!overview.data.available && <p className="ai-error">{t("admin.noKey")}</p>}
          <div className="admin-tiles">
            <StatTile label={t("admin.model")} value={overview.data.model} />
            <StatTile label={t("admin.monthTokens")} value={fmt.number(overview.data.month_tokens, 0)} />
            <StatTile label={t("admin.monthCost")} value={t("admin.cost", { value: fmt.number(overview.data.month_cost_usd, 2, 2) })} />
          </div>
          <Input label={t("admin.search")} type="search" value={search} onChange={(event) => setSearch(event.target.value)} />
          <DataTable
            columns={columns}
            rows={overview.data.rows}
            getRowId={(row) => row.athlete_id}
            caption={t("admin.title")}
            empty={<EmptyState title={q ? t("admin.noMatch") : t("admin.none")} />}
          />
        </div>
      )}
    </Card>
  );
}
