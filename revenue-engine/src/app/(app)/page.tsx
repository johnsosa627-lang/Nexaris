import Link from "next/link";
import { Badge, Card, DemoBadge, Empty, PageHeader, Stat, stageTone } from "@/components/ui";
import { t } from "@/i18n";
import { STAGES } from "@/lib/catalog";
import { formatDateTime } from "@/lib/format";
import { requireCtx } from "@/lib/session";
import { getDashboard } from "@/server/crm";

export const metadata = { title: "Panel" };

const alertStyles = {
  danger: "border-red-200 bg-red-50 text-red-800",
  warning: "border-amber-200 bg-amber-50 text-amber-900",
  info: "border-indigo-200 bg-indigo-50 text-indigo-900",
};

export default async function DashboardPage() {
  const ctx = await requireCtx();
  const d = await getDashboard(ctx);

  return (
    <>
      <PageHeader
        title="Panel principal"
        subtitle="Resumen de tu actividad comercial. Solo se muestran datos registrados; nada estimado."
        actions={
          <Link href="/empresas/nueva" className="btn btn-primary">
            + Nueva empresa
          </Link>
        }
      />

      {d.alerts.length > 0 ? (
        <div className="mb-6 space-y-2">
          {d.alerts.map((a) => (
            <div key={a.text} className={`rounded-lg border px-4 py-2 text-sm ${alertStyles[a.kind]}`}>
              {a.href ? (
                <Link href={a.href} className="hover:underline">
                  {a.text}
                </Link>
              ) : (
                a.text
              )}
            </div>
          ))}
        </div>
      ) : null}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <Stat label="Clientes activos" value={d.activeClients} href="/empresas?etapa=cliente" />
        <Stat label="Prospectos nuevos" value={d.newProspects} hint="Últimos 30 días" href="/empresas" />
        <Stat label="Oportunidades abiertas" value={d.openOpportunities} hint="Respondió → negociación" />
        <Stat
          label="Seguimientos"
          value={d.pendingFollowUps}
          hint={d.overdueFollowUps ? `${d.overdueFollowUps} vencido(s)` : "Al día"}
          tone={d.overdueFollowUps ? "warning" : "default"}
          href="/seguimientos"
        />
        <Stat
          label="Aprobaciones"
          value={d.pendingApprovals}
          hint="Esperando decisión"
          tone={d.pendingApprovals ? "warning" : "default"}
          href="/aprobaciones"
        />
        <Stat label="Empresas en el CRM" value={d.totalCompanies} href="/empresas" />
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
        <Stat label="Ingresos del negocio" value="Sin datos" tone="muted" hint="Se registran en la Fase 5 (finanzas)" />
        <Stat label="Comisiones pendientes" value="Sin datos" tone="muted" hint="Se calculan en la Fase 5" />
        <Stat label="Resultados comerciales" value="Sin datos" tone="muted" hint="Se miden con clientes (Fase 4)" />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <Card title="Embudo por etapa" className="lg:col-span-1">
          {d.totalCompanies === 0 ? (
            <Empty>Todavía no cargaste empresas.</Empty>
          ) : (
            <ul className="space-y-1.5">
              {STAGES.map((s) => (
                <li key={s}>
                  <Link
                    href={`/empresas?etapa=${s}`}
                    className="flex items-center justify-between rounded px-1 py-0.5 text-sm hover:bg-slate-50"
                  >
                    <Badge tone={stageTone(s)}>{t.stages[s]}</Badge>
                    <span className="font-semibold text-slate-700">{d.byStage[s]}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Próximos seguimientos" actions={<Link href="/seguimientos" className="text-sm text-indigo-700">Ver todos</Link>}>
          {d.upcoming.length === 0 ? (
            <Empty>No hay seguimientos pendientes.</Empty>
          ) : (
            <ul className="divide-y divide-slate-100">
              {d.upcoming.map(({ followUp: f, companyName, overdue }) => (
                <li key={f.id} className="py-2 text-sm">
                  <Link href={`/empresas/${f.companyId}`} className="font-medium hover:underline">
                    {f.title}
                  </Link>
                  <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                    <span>{companyName}</span>
                    <span className={overdue ? "font-semibold text-red-600" : ""}>
                      {formatDateTime(f.dueAt)}
                    </span>
                    {f.isDemo ? <DemoBadge /> : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Actividad reciente">
          {d.recentActivity.length === 0 ? (
            <Empty>Sin actividad todavía.</Empty>
          ) : (
            <ul className="divide-y divide-slate-100">
              {d.recentActivity.map(({ activity: a, companyName }) => (
                <li key={a.id} className="py-2 text-sm">
                  <Link href={`/empresas/${a.companyId}`} className="font-medium hover:underline">
                    {a.title}
                  </Link>
                  <div className="text-xs text-slate-500">
                    {companyName} · {t.activityTypes[a.type as keyof typeof t.activityTypes] ?? a.type} ·{" "}
                    {formatDateTime(a.occurredAt)}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}
