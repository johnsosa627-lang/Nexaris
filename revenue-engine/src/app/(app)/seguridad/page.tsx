import { ActionForm, Submit } from "@/components/action-form";
import { Badge, Card, Empty, PageHeader, levelTone } from "@/components/ui";
import { t } from "@/i18n";
import { ACTION_TYPES, type ActionType, type Level } from "@/lib/catalog";
import { formatDateTime } from "@/lib/format";
import { requireCtx } from "@/lib/session";
import { getWorkspace, getPolicyLevels, listAudit, listSuppressions } from "@/server/security";
import {
  addSuppressionAction,
  clearDemoAction,
  limitsAction,
  loadDemoAction,
  pauseAction,
  policyAction,
  removeSuppressionAction,
  resumeAction,
} from "./actions";

export const metadata = { title: "Seguridad" };

const AUDIT_LABELS: Record<string, string> = {
  "setup.completado": "Instalación inicial",
  "setup.codigo_incorrecto": "Código de instalación incorrecto",
  "login.correcto": "Inicio de sesión",
  "login.fallido": "Inicio de sesión fallido",
  logout: "Cierre de sesión",
  "empresa.creada": "Empresa creada",
  "empresa.editada": "Empresa editada",
  "empresa.etapa_cambiada": "Cambio de etapa",
  "contacto.creado": "Contacto creado",
  "contacto.baja": "Baja de contacto",
  "seguimiento.creado": "Seguimiento creado",
  "automatizaciones.detenidas": "Automatizaciones DETENIDAS",
  "automatizaciones.reanudadas": "Automatizaciones reanudadas",
  "limites.actualizados": "Límites cambiados",
  "nivel_autonomia.cambiado": "Nivel de autonomía cambiado",
  "exclusion.agregada": "Agregado a exclusión",
  "exclusion.quitada": "Quitado de exclusión",
  "accion.automatica": "Acción automática (Nivel 1)",
  "accion.bloqueada": "Acción bloqueada",
  "aprobacion.solicitada": "Aprobación solicitada",
  "aprobacion.aprobada": "Aprobación concedida",
  "aprobacion.rechazada": "Aprobación rechazada",
  "aprobacion.ejecutada": "Acción ejecutada",
  "aprobacion.fallida": "Acción fallida",
  "agente.configurado": "Agente configurado",
  "datos_prueba.cargados": "Datos de prueba cargados",
  "datos_prueba.borrados": "Datos de prueba borrados",
  "diagnostico.pedido": "Diagnóstico pedido",
  "diagnostico.listo": "Diagnóstico listo",
  "diagnostico.fallido": "Diagnóstico fallido",
};

export default async function SecurityPage() {
  const ctx = await requireCtx();
  const [ws, levels, suppressions, audit] = await Promise.all([
    getWorkspace(ctx),
    getPolicyLevels(ctx.workspaceId),
    listSuppressions(ctx),
    listAudit(ctx, { limit: 100 }),
  ]);
  const isOwner = ctx.role === "owner";
  const byLevel = ([1, 2, 3] as Level[]).map((lvl) => ({
    lvl,
    items: (Object.keys(ACTION_TYPES) as ActionType[]).filter((a) => levels[a] === lvl),
  }));

  return (
    <>
      <PageHeader title="Seguridad" subtitle="Botón de parada, niveles de autonomía, límites, lista de exclusión y registro de todo lo que pasa." />

      <div className="space-y-4">
        <Card title="Botón de parada" className={ws.automationsPaused ? "border-red-300" : ""}>
          {ws.automationsPaused ? (
            <>
              <p className="text-sm text-red-700">
                <strong>Detenidas</strong> desde {formatDateTime(ws.pausedAt)}. Motivo: {ws.pausedReason}
              </p>
              <p className="mt-1 text-sm text-slate-600">Ningún agente puede actuar ni ejecutar acciones aprobadas.</p>
              {isOwner ? (
                <ActionForm action={resumeAction} className="mt-3" confirm="¿Reanudar las automatizaciones?">
                  <Submit>Reanudar automatizaciones</Submit>
                </ActionForm>
              ) : (
                <p className="mt-2 text-xs text-slate-500">Solo el dueño puede reanudarlas.</p>
              )}
            </>
          ) : (
            <>
              <p className="text-sm text-slate-700">
                Las automatizaciones están <strong>funcionando</strong>. Si algo parece raro, detenelas: cualquier persona del equipo puede hacerlo.
              </p>
              <ActionForm action={pauseAction} className="mt-3 flex flex-col gap-2 sm:flex-row" confirm="¿Detener TODAS las automatizaciones?">
                <input className="field sm:max-w-sm" name="reason" placeholder="Motivo (opcional)" />
                <Submit variant="danger">Detener todo</Submit>
              </ActionForm>
            </>
          )}
        </Card>

        <Card title="Niveles de autonomía">
          <p className="mb-3 text-sm text-slate-600">
            Podés subir el nivel de una acción para tener más control. Nunca se puede bajar por debajo del mínimo de seguridad.
          </p>
          <div className="grid gap-3 md:grid-cols-3">
            {byLevel.map(({ lvl, items }) => (
              <div key={lvl} className="rounded-lg border border-slate-200 p-3">
                <Badge tone={levelTone(lvl)}>{t.levels[lvl]}</Badge>
                <ul className="mt-2 space-y-1 text-sm">
                  {items.map((a) => (
                    <li key={a}>{t.actionTypes[a]}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          {isOwner ? (
            <ActionForm action={policyAction} className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-end">
              <div className="flex-1">
                <label className="label" htmlFor="actionType">Acción</label>
                <select className="field" id="actionType" name="actionType">
                  {(Object.keys(ACTION_TYPES) as ActionType[]).map((a) => (
                    <option key={a} value={a}>
                      {t.actionTypes[a]} (mínimo {ACTION_TYPES[a].minLevel})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label" htmlFor="level">Nivel</label>
                <select className="field" id="level" name="level" defaultValue="2">
                  <option value="1">1</option>
                  <option value="2">2</option>
                  <option value="3">3</option>
                </select>
              </div>
              <Submit variant="secondary">Cambiar nivel</Submit>
            </ActionForm>
          ) : null}
        </Card>

        <Card title="Límites de gasto y envíos">
          <ActionForm action={limitsAction} className="grid gap-3 sm:grid-cols-3">
            <div>
              <label className="label" htmlFor="aiMonthlyBudget">Tope mensual de IA (US$)</label>
              <input className="field" id="aiMonthlyBudget" name="aiMonthlyBudget" inputMode="decimal" defaultValue={(ws.aiMonthlyBudgetCents / 100).toString()} disabled={!isOwner} />
            </div>
            <div>
              <label className="label" htmlFor="maxSpendPerAction">Gasto máximo por acción (US$)</label>
              <input className="field" id="maxSpendPerAction" name="maxSpendPerAction" inputMode="decimal" defaultValue={(ws.maxSpendPerActionCents / 100).toString()} disabled={!isOwner} />
            </div>
            <div>
              <label className="label" htmlFor="dailyEmailLimit">Máximo de correos por día</label>
              <input className="field" id="dailyEmailLimit" name="dailyEmailLimit" type="number" min={0} max={500} defaultValue={ws.dailyEmailLimit} disabled={!isOwner} />
            </div>
            <p className="text-xs text-slate-500 sm:col-span-3">
              El tope de IA y de correos se aplican desde las Etapas 1B y 2, cuando esas funciones existan. Toda acción que cueste dinero es siempre de Nivel 3.
            </p>
            {isOwner ? (
              <div className="sm:col-span-3">
                <Submit variant="secondary">Guardar límites</Submit>
              </div>
            ) : null}
          </ActionForm>
        </Card>

        <Card title={`Lista de exclusión (${suppressions.length})`}>
          <p className="mb-3 text-sm text-slate-600">
            Emails o dominios a los que el sistema nunca les va a escribir. Un dominio (ej. empresa.com) bloquea todos sus emails.
          </p>
          <ActionForm action={addSuppressionAction} resetOnSuccess className="mb-4 flex flex-col gap-2 sm:flex-row">
            <input className="field" name="value" placeholder="email@empresa.com o empresa.com" required />
            <input className="field" name="reason" placeholder="Motivo (opcional)" />
            <Submit variant="secondary">Agregar</Submit>
          </ActionForm>
          {suppressions.length === 0 ? (
            <Empty>La lista está vacía.</Empty>
          ) : (
            <ul className="divide-y divide-slate-100 text-sm">
              {suppressions.map((s) => (
                <li key={s.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                  <div>
                    <span className="font-medium">{s.value}</span> <Badge>{s.kind}</Badge>
                    <div className="text-xs text-slate-500">
                      {s.reason ?? "Sin motivo"} · {formatDateTime(s.createdAt)}
                    </div>
                  </div>
                  {isOwner ? (
                    <ActionForm action={removeSuppressionAction} confirm={`¿Quitar ${s.value} de la lista de exclusión?`}>
                      <input type="hidden" name="id" value={s.id} />
                      <Submit size="sm" variant="secondary">
                        Quitar
                      </Submit>
                    </ActionForm>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Datos de prueba" id="datos-prueba">
          <p className="mb-3 text-sm text-slate-600">
            Cargá 5 empresas inventadas (marcadas PRUEBA) para practicar. Se borran de una vez sin tocar tus datos reales.
          </p>
          {isOwner ? (
            <div className="flex flex-wrap gap-2">
              <ActionForm action={loadDemoAction}>
                <Submit variant="secondary">Cargar datos de prueba</Submit>
              </ActionForm>
              <ActionForm action={clearDemoAction} confirm="¿Borrar todos los datos de prueba?">
                <Submit variant="danger">Borrar datos de prueba</Submit>
              </ActionForm>
            </div>
          ) : (
            <p className="text-xs text-slate-500">Solo el dueño puede hacerlo.</p>
          )}
        </Card>

        <Card title="Registro de actividad (últimos 100)">
          {audit.length === 0 ? (
            <Empty>Sin registros.</Empty>
          ) : (
            <ul className="divide-y divide-slate-100 text-sm">
              {audit.map((a) => (
                <li key={a.id} className="py-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{AUDIT_LABELS[a.action] ?? a.action}</span>
                    {a.entityId ? <span className="break-all text-xs text-slate-500">{a.entityId}</span> : null}
                  </div>
                  <div className="text-xs text-slate-500">
                    {formatDateTime(a.at)} · {a.actorType === "agent" ? `agente ${a.actorId}` : a.actorType === "user" ? "usuario" : a.actorType}
                    {a.ip ? ` · IP ${a.ip}` : ""}
                  </div>
                  {a.details ? (
                    <details className="text-xs">
                      <summary className="cursor-pointer text-slate-500">detalle</summary>
                      <pre className="mt-1 overflow-x-auto rounded bg-slate-50 p-2">{JSON.stringify(a.details, null, 2)}</pre>
                    </details>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}
