import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Badge, Card, DataTable, EmptyState, SkeletonGroup, StatTile, type DataTableColumn } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import type { AdminUserRow, FailedRun, WorkerState, WorkerStatus } from "./types";
import { useAdminOverview } from "./useAdmin";
import "./Admin.css";

const WORKER_TONE = { ok: "positive", stale: "negative", never: "neutral" } as const satisfies Record<WorkerState, string>;

function WorkerCard({ worker }: { worker: WorkerStatus }) {
  const { t } = useTranslation("admin");
  const fmt = useFormat();
  return (
    <Card as="section" title={t("worker.title")}>
      <div className="admin-worker">
        <div>
          <Badge tone={WORKER_TONE[worker.state]}>{t(`worker.state.${worker.state}`)}</Badge>
        </div>
        {worker.state === "never" ? (
          <p className="admin-error">{t("worker.never")}</p>
        ) : (
          <dl className="admin-worker__facts">
            <div>
              <dt>{t("worker.lastSeen")}</dt>
              <dd>{fmt.relative(worker.last_seen_at)}</dd>
            </div>
            <div>
              <dt>{t("worker.started")}</dt>
              <dd>{fmt.relative(worker.started_at)}</dd>
            </div>
            <div>
              <dt>{t("worker.lastPoll")}</dt>
              <dd>
                {worker.last_poll_finished_at
                  ? t("worker.pollSummary", {
                      when: fmt.relative(worker.last_poll_finished_at),
                      count: worker.last_poll_connections ?? 0,
                      failures: worker.last_poll_failures ?? 0,
                    })
                  : t("worker.noPoll")}
              </dd>
            </div>
          </dl>
        )}
        {worker.last_error && <p className="admin-error">{worker.last_error}</p>}
      </div>
    </Card>
  );
}

export function AdminOverviewPanel() {
  const { t } = useTranslation("admin");
  const fmt = useFormat();
  const overview = useAdminOverview();

  if (overview.isLoading) return <SkeletonGroup lines={6} />;
  if (overview.isError || !overview.data) {
    return <EmptyState title={t("loadFailed")} description={errorMessage(overview.error)} />;
  }
  const { worker, counts, recent_users, failed_runs } = overview.data;

  const userColumns: DataTableColumn<AdminUserRow>[] = [
    {
      id: "user",
      header: t("users.user"),
      primary: true,
      cell: (row) => (
        <>
          {row.display_name ?? "—"}
          <br />
          <span className="admin-muted">{row.email}</span>
        </>
      ),
    },
    { id: "joined", header: t("users.joined"), cell: (row) => fmt.date(row.created_at) },
    {
      id: "flags",
      header: t("users.status"),
      cell: (row) => (
        <>
          {row.is_platform_admin && <Badge tone="accent">{t("users.admin")}</Badge>}
          {!row.is_active && <Badge tone="negative">{t("users.inactive")}</Badge>}
        </>
      ),
    },
  ];

  const runColumns: DataTableColumn<FailedRun>[] = [
    { id: "transponder", header: t("failures.transponder"), primary: true, cell: (row) => row.transponder },
    { id: "when", header: t("failures.when"), cell: (row) => fmt.relative(row.requested_at) },
    { id: "http", header: t("failures.http"), cell: (row) => row.http_status ?? "—" },
    { id: "error", header: t("failures.error"), cell: (row) => row.error_message ?? "—" },
  ];

  return (
    <div className="admin-stack">
      <div className="admin-tiles">
        <StatTile label={t("counts.users")} value={counts.users} />
        <StatTile label={t("counts.athletes")} value={counts.athletes} />
        <StatTile label={t("counts.clubs")} value={counts.clubs} />
        <StatTile label={t("counts.transponders")} value={counts.active_transponders} />
      </div>
      <WorkerCard worker={worker} />
      <Card as="section" title={t("failures.title")}>
        <DataTable
          columns={runColumns}
          rows={failed_runs}
          getRowId={(row) => row.id}
          caption={t("failures.title")}
          empty={<EmptyState title={t("failures.none")} />}
        />
      </Card>
      <Card as="section" title={t("users.title")}>
        <DataTable columns={userColumns} rows={recent_users} getRowId={(row) => row.id} caption={t("users.title")} />
      </Card>
    </div>
  );
}
