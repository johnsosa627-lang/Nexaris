import Link from "next/link";
import { ActionForm, Submit } from "@/components/action-form";
import { Card, DemoBadge, Empty, PageHeader } from "@/components/ui";
import { formatDateTime } from "@/lib/format";
import { requireCtx } from "@/lib/session";
import { listFollowUps } from "@/server/crm";
import { closeFollowUpAction } from "../empresas/actions";

export const metadata = { title: "Seguimientos" };

export default async function FollowUpsPage() {
  const ctx = await requireCtx();
  const rows = await listFollowUps(ctx);
  const overdue = rows.filter((r) => r.overdue);
  const upcoming = rows.filter((r) => !r.overdue);

  const list = (items: typeof rows) => (
    <ul className="divide-y divide-slate-100">
      {items.map(({ followUp: f, companyName, companyId }) => (
        <li key={f.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2 font-medium">
              {f.title} {f.isDemo ? <DemoBadge /> : null}
            </div>
            <div className="text-xs text-slate-500">
              <Link href={`/empresas/${companyId}`} className="text-indigo-700 hover:underline">
                {companyName}
              </Link>{" "}
              · {formatDateTime(f.dueAt)}
            </div>
          </div>
          <ActionForm action={closeFollowUpAction} className="flex gap-2">
            <input type="hidden" name="followUpId" value={f.id} />
            <Submit size="sm" name="status" value="hecho">
              Hecho
            </Submit>
            <Submit size="sm" variant="secondary" name="status" value="cancelado">
              Cancelar
            </Submit>
          </ActionForm>
        </li>
      ))}
    </ul>
  );

  return (
    <>
      <PageHeader
        title="Seguimientos"
        subtitle="Tareas comerciales pendientes. Los seguimientos se crean desde la ficha de cada empresa."
      />
      {rows.length === 0 ? (
        <Empty>No hay seguimientos pendientes.</Empty>
      ) : (
        <div className="space-y-4">
          {overdue.length > 0 ? <Card title={`Vencidos (${overdue.length})`}>{list(overdue)}</Card> : null}
          <Card title={`Próximos (${upcoming.length})`}>
            {upcoming.length ? list(upcoming) : <Empty>Nada programado hacia adelante.</Empty>}
          </Card>
        </div>
      )}
    </>
  );
}
