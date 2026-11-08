import Link from "next/link";
import { ActionForm, Submit } from "@/components/action-form";
import { Badge, Card, DemoBadge, Empty, PageHeader, levelTone } from "@/components/ui";
import { t } from "@/i18n";
import type { ActionType, ApprovalStatus, Level } from "@/lib/catalog";
import { getAgent } from "@/lib/catalog";
import { formatDateTime } from "@/lib/format";
import { requireCtx } from "@/lib/session";
import { LEVEL3_CONFIRMATION, listApprovals } from "@/server/gateway";
import { decideAction } from "./actions";

export const metadata = { title: "Aprobaciones" };

function requester(type: string, id: string | null) {
  if (type === "agent" && id) {
    const a = getAgent(id);
    return a ? t.agents[a.key as keyof typeof t.agents].name : id;
  }
  return type === "user" ? "Una persona del equipo" : "Sistema";
}

export default async function ApprovalsPage() {
  const ctx = await requireCtx();
  const all = await listApprovals(ctx);
  const pending = all.filter((a) => a.status === "pendiente");
  const history = all.filter((a) => a.status !== "pendiente");

  return (
    <>
      <PageHeader
        title="Aprobaciones"
        subtitle="Acciones de Nivel 2 y 3 que un agente quiere hacer. Nada sale del sistema sin tu decisión."
      />

      <Card title={`Pendientes (${pending.length})`} className="mb-4">
        {pending.length === 0 ? (
          <Empty>No hay acciones esperando aprobación.</Empty>
        ) : (
          <ul className="space-y-3">
            {pending.map((a) => (
              <li key={a.id} className="rounded-lg border border-slate-200 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={levelTone(a.level)}>{t.levels[a.level as Level]}</Badge>
                  <span className="text-sm font-semibold">{t.actionTypes[a.actionType as ActionType] ?? a.actionType}</span>
                  {a.isDemo ? <DemoBadge /> : null}
                </div>
                <p className="mt-1 text-sm text-slate-800">{a.summary}</p>
                <div className="mt-1 text-xs text-slate-500">
                  Pedido por {requester(a.requestedByType, a.requestedById)} · {formatDateTime(a.createdAt)}
                  {a.companyId ? (
                    <>
                      {" "}
                      ·{" "}
                      <Link href={`/empresas/${a.companyId}`} className="text-indigo-700 hover:underline">
                        ver empresa
                      </Link>
                    </>
                  ) : null}
                </div>
                <details className="mt-2 text-xs">
                  <summary className="cursor-pointer text-slate-600">Ver datos técnicos</summary>
                  <pre className="mt-1 overflow-x-auto rounded bg-slate-50 p-2">{JSON.stringify(a.payload, null, 2)}</pre>
                </details>
                <ActionForm action={decideAction} className="mt-3 space-y-2">
                  <input type="hidden" name="approvalId" value={a.id} />
                  <input className="field" name="note" placeholder="Comentario (opcional)" />
                  {a.level === 3 ? (
                    <div>
                      <label className="label" htmlFor={`conf-${a.id}`}>
                        Acción restringida: para autorizarla escribí {LEVEL3_CONFIRMATION} (solo el dueño)
                      </label>
                      <input className="field" id={`conf-${a.id}`} name="confirmation" autoComplete="off" />
                    </div>
                  ) : null}
                  <div className="flex gap-2">
                    <Submit name="decision" value="aprobar">
                      Aprobar
                    </Submit>
                    <Submit variant="secondary" name="decision" value="rechazar">
                      Rechazar
                    </Submit>
                  </div>
                </ActionForm>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Historial">
        {history.length === 0 ? (
          <Empty>Todavía no se decidió ninguna acción.</Empty>
        ) : (
          <ul className="divide-y divide-slate-100">
            {history.map((a) => (
              <li key={a.id} className="py-2 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={a.status === "ejecutada" ? "green" : a.status === "rechazada" || a.status === "fallida" ? "red" : "indigo"}>
                    {t.approvalStatuses[a.status as ApprovalStatus] ?? a.status}
                  </Badge>
                  <span className="font-medium">{t.actionTypes[a.actionType as ActionType] ?? a.actionType}</span>
                  {a.isDemo ? <DemoBadge /> : null}
                  <span className="text-xs text-slate-500">{formatDateTime(a.decidedAt)}</span>
                </div>
                <div className="text-slate-700">{a.summary}</div>
                {a.result ? (
                  <div className="text-xs text-slate-500">
                    {(a.result as { nota?: string; error?: string }).nota ?? (a.result as { error?: string }).error ?? ""}
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}
