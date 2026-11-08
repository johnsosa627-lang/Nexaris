import Link from "next/link";
import { Badge, Card, DemoBadge, Empty, PageHeader, stageTone } from "@/components/ui";
import { t } from "@/i18n";
import { STAGES, type Stage } from "@/lib/catalog";
import { formatDate } from "@/lib/format";
import { requireCtx } from "@/lib/session";
import { listCompanies } from "@/server/crm";

export const metadata = { title: "Empresas" };

export default async function CompaniesPage({ searchParams }: PageProps<"/empresas">) {
  const ctx = await requireCtx();
  const sp = await searchParams;
  const q = typeof sp.q === "string" ? sp.q : "";
  const etapa = typeof sp.etapa === "string" ? sp.etapa : "";
  const rows = await listCompanies(ctx, { q, stage: etapa });

  return (
    <>
      <PageHeader
        title="Empresas"
        subtitle="Prospectos y clientes. Tocá una empresa para ver su ficha e historial."
        actions={
          <Link href="/empresas/nueva" className="btn btn-primary">
            + Nueva empresa
          </Link>
        }
      />
      <Card className="mb-4">
        <form className="flex flex-col gap-3 sm:flex-row sm:items-end" method="get">
          <div className="flex-1">
            <label className="label" htmlFor="q">Buscar</label>
            <input className="field" id="q" name="q" defaultValue={q} placeholder="Nombre, sitio, ciudad o sector" />
          </div>
          <div className="sm:w-56">
            <label className="label" htmlFor="etapa">Etapa</label>
            <select className="field" id="etapa" name="etapa" defaultValue={etapa}>
              <option value="">Todas</option>
              {STAGES.map((s) => (
                <option key={s} value={s}>
                  {t.stages[s]}
                </option>
              ))}
            </select>
          </div>
          <button className="btn btn-secondary">Filtrar</button>
        </form>
      </Card>

      {rows.length === 0 ? (
        <Empty>
          {q || etapa ? "No hay empresas con ese filtro." : "Todavía no hay empresas. Cargá la primera con “+ Nueva empresa”."}
        </Empty>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <ul className="divide-y divide-slate-100">
            {rows.map((c) => (
              <li key={c.id}>
                <Link href={`/empresas/${c.id}`} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 hover:bg-slate-50">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2 font-semibold text-slate-900">
                      <span className="truncate">{c.name}</span>
                      {c.isDemo ? <DemoBadge /> : null}
                    </div>
                    <div className="truncate text-xs text-slate-500">
                      {[c.domain, c.sector, c.city, c.country].filter(Boolean).join(" · ") || "Sin datos adicionales"}
                    </div>
                  </div>
                  <Badge tone={stageTone(c.stage)}>{t.stages[c.stage as Stage] ?? c.stage}</Badge>
                  <span className="text-xs text-slate-400">Actualizada {formatDate(c.updatedAt)}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="mt-3 text-xs text-slate-500">{rows.length} empresa(s).</p>
    </>
  );
}
