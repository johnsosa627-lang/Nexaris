import Link from "next/link";
import { notFound } from "next/navigation";
import { ActionForm, Submit } from "@/components/action-form";
import { CompanyFields } from "@/components/company-fields";
import { Badge, Card, DemoBadge, Empty, stageTone } from "@/components/ui";
import { t } from "@/i18n";
import { CONTACT_SOURCES, MANUAL_ACTIVITY_TYPES, STAGES, type Stage } from "@/lib/catalog";
import { formatDate, formatDateTime } from "@/lib/format";
import { requireCtx } from "@/lib/session";
import { DiagnosisCard } from "@/components/diagnosis-card";
import { getCompanyDetail } from "@/server/crm";
import { getDiagnoses } from "@/server/diagnosis";
import { UserError } from "@/server/errors";
import {
  addActivityAction,
  addContactAction,
  addFollowUpAction,
  changeStageAction,
  closeFollowUpAction,
  optOutContactAction,
  updateCompanyAction,
} from "../actions";

/** Fecha para un campo datetime-local en hora de Montevideo (UTC-3). */
function localInput(d: Date) {
  return new Date(d.getTime() - 3 * 3600_000).toISOString().slice(0, 16);
}

export default async function CompanyPage({ params }: PageProps<"/empresas/[id]">) {
  const ctx = await requireCtx();
  const { id } = await params;
  let detail;
  try {
    detail = await getCompanyDetail(ctx, id);
  } catch (err) {
    if (err instanceof UserError) notFound();
    throw err;
  }
  const { company: c, contacts, activities, followUps, suggestedDueAt } = detail;
  const diag = await getDiagnoses(ctx, c.id);
  const pendingFollowUps = followUps.filter((f) => f.status === "pendiente");

  const contactOptions = (
    <>
      <option value="">— Sin contacto específico —</option>
      {contacts.map((ct) => (
        <option key={ct.id} value={ct.id}>
          {ct.name}
        </option>
      ))}
    </>
  );

  return (
    <>
      <div className="mb-2 text-sm">
        <Link href="/empresas" className="text-indigo-700 hover:underline">
          ← Empresas
        </Link>
      </div>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="flex flex-wrap items-center gap-2 text-2xl font-bold tracking-tight">
            {c.name} {c.isDemo ? <DemoBadge /> : null}
          </h1>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-slate-600">
            <Badge tone={stageTone(c.stage)}>{t.stages[c.stage as Stage] ?? c.stage}</Badge>
            {c.website ? (
              <a href={c.website} target="_blank" rel="noopener noreferrer nofollow" className="text-indigo-700 hover:underline">
                {c.domain}
              </a>
            ) : (
              <span>Sin sitio web</span>
            )}
            {[c.sector, c.city, c.country].filter(Boolean).map((x) => (
              <span key={x}>· {x}</span>
            ))}
          </div>
          <div className="mt-1 text-xs text-slate-500">
            Origen: {t.companySources[c.source as keyof typeof t.companySources] ?? c.source} · Alta {formatDate(c.createdAt)} ·
            Puntuación de oportunidad: {c.opportunityScore ?? "sin calcular"}
          </div>
        </div>
        <ActionForm action={changeStageAction} className="flex items-end gap-2">
          <input type="hidden" name="companyId" value={c.id} />
          <div>
            <label className="label" htmlFor="stage">Etapa</label>
            <select className="field" id="stage" name="stage" defaultValue={c.stage}>
              {STAGES.map((s) => (
                <option key={s} value={s}>
                  {t.stages[s]}
                </option>
              ))}
            </select>
          </div>
          <Submit variant="secondary">Cambiar</Submit>
        </ActionForm>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <DiagnosisCard
            companyId={c.id}
            hasWebsite={!!c.website}
            latest={diag.latestDone}
            findings={diag.latestFindings}
            pending={diag.pending}
            history={diag.list}
            existingEmails={contacts.map((ct) => ct.email ?? "").filter(Boolean)}
          />

          <Card title="Registrar actividad">
            <ActionForm action={addActivityAction} resetOnSuccess className="space-y-3">
              <input type="hidden" name="companyId" value={c.id} />
              <div className="grid gap-3 sm:grid-cols-3">
                <div>
                  <label className="label" htmlFor="type">Tipo</label>
                  <select className="field" id="type" name="type" defaultValue="nota">
                    {MANUAL_ACTIVITY_TYPES.map((tp) => (
                      <option key={tp} value={tp}>
                        {t.activityTypes[tp]}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label" htmlFor="act-contact">Contacto</label>
                  <select className="field" id="act-contact" name="contactId">
                    {contactOptions}
                  </select>
                </div>
                <div>
                  <label className="label" htmlFor="occurredAt">Cuándo (vacío = ahora)</label>
                  <input className="field" id="occurredAt" name="occurredAt" type="datetime-local" />
                </div>
              </div>
              <div>
                <label className="label" htmlFor="title">Resumen *</label>
                <input className="field" id="title" name="title" required minLength={2} placeholder="Ej: Llamé al gerente, pidió propuesta por email" />
              </div>
              <div>
                <label className="label" htmlFor="body">Detalle</label>
                <textarea className="field" id="body" name="body" rows={3} />
              </div>
              <Submit>Registrar</Submit>
            </ActionForm>
          </Card>

          <Card title={`Historial (${activities.length})`}>
            {activities.length === 0 ? (
              <Empty>Sin actividad registrada.</Empty>
            ) : (
              <ol className="space-y-3">
                {activities.map((a) => (
                  <li key={a.id} className="border-l-2 border-slate-200 pl-3">
                    <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                      <Badge>{t.activityTypes[a.type as keyof typeof t.activityTypes] ?? a.type}</Badge>
                      <span>{formatDateTime(a.occurredAt)}</span>
                      <span>· {a.actorName}</span>
                    </div>
                    <div className="mt-0.5 text-sm font-medium text-slate-900">{a.title}</div>
                    {a.body ? <p className="mt-0.5 whitespace-pre-wrap text-sm text-slate-700">{a.body}</p> : null}
                  </li>
                ))}
              </ol>
            )}
          </Card>
        </div>

        <div className="space-y-4">
          <Card title={`Seguimientos pendientes (${pendingFollowUps.length})`}>
            {pendingFollowUps.length === 0 ? (
              <p className="mb-3 text-sm text-slate-500">No hay seguimientos pendientes.</p>
            ) : (
              <ul className="mb-4 space-y-2">
                {pendingFollowUps.map((f) => (
                  <li key={f.id} className="rounded-lg border border-slate-200 p-2 text-sm">
                    <div className="font-medium">{f.title}</div>
                    <div className={`text-xs ${f.overdue ? "font-semibold text-red-600" : "text-slate-500"}`}>
                      {formatDateTime(f.dueAt)} {f.overdue ? "(vencido)" : ""}
                    </div>
                    <ActionForm action={closeFollowUpAction} className="mt-2 flex gap-2">
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
            )}
            <ActionForm action={addFollowUpAction} resetOnSuccess className="space-y-3 border-t border-slate-100 pt-3">
              <input type="hidden" name="companyId" value={c.id} />
              <div>
                <label className="label" htmlFor="fu-title">Nuevo seguimiento *</label>
                <input className="field" id="fu-title" name="title" required minLength={2} placeholder="Ej: Llamar para coordinar reunión" />
              </div>
              <div>
                <label className="label" htmlFor="dueAt">Fecha y hora *</label>
                <input className="field" id="dueAt" name="dueAt" type="datetime-local" required defaultValue={localInput(suggestedDueAt)} />
              </div>
              <div>
                <label className="label" htmlFor="fu-contact">Contacto</label>
                <select className="field" id="fu-contact" name="contactId">
                  {contactOptions}
                </select>
              </div>
              <Submit>Programar</Submit>
            </ActionForm>
          </Card>

          <Card title={`Contactos (${contacts.length})`}>
            {contacts.length === 0 ? (
              <p className="mb-3 text-sm text-slate-500">Sin contactos.</p>
            ) : (
              <ul className="mb-4 space-y-2">
                {contacts.map((ct) => (
                  <li key={ct.id} className="rounded-lg border border-slate-200 p-2 text-sm">
                    <div className="flex flex-wrap items-center gap-2 font-medium">
                      {ct.name}
                      {ct.suppressed ? <Badge tone="red">No contactar</Badge> : null}
                    </div>
                    {ct.roleTitle ? <div className="text-xs text-slate-500">{ct.roleTitle}</div> : null}
                    {ct.email ? <div className="break-all text-xs">{ct.email}</div> : null}
                    {ct.phone ? <div className="text-xs">{ct.phone}</div> : null}
                    {ct.source ? (
                      <div className="mt-1 text-xs text-slate-500">
                        Origen: {t.contactSources[ct.source as keyof typeof t.contactSources] ?? ct.source}
                        {ct.sourceUrl ? (
                          <>
                            {" "}
                            ·{" "}
                            <a className="text-indigo-700 hover:underline" href={ct.sourceUrl} target="_blank" rel="noopener noreferrer nofollow">
                              ver fuente
                            </a>
                          </>
                        ) : null}
                      </div>
                    ) : null}
                    {!ct.optedOut ? (
                      <ActionForm
                        action={optOutContactAction}
                        className="mt-2"
                        confirm={`¿Registrar que ${ct.name} pidió no recibir más mensajes? Su email irá a la lista de exclusión.`}
                      >
                        <input type="hidden" name="companyId" value={c.id} />
                        <input type="hidden" name="contactId" value={ct.id} />
                        <Submit size="sm" variant="secondary">
                          Registrar baja
                        </Submit>
                      </ActionForm>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
            <details className="border-t border-slate-100 pt-3">
              <summary className="cursor-pointer text-sm font-semibold text-indigo-700">+ Agregar contacto</summary>
              <ActionForm action={addContactAction} resetOnSuccess className="mt-3 space-y-3">
                <input type="hidden" name="companyId" value={c.id} />
                <div>
                  <label className="label" htmlFor="ct-name">Nombre *</label>
                  <input className="field" id="ct-name" name="name" required minLength={2} />
                </div>
                <div>
                  <label className="label" htmlFor="roleTitle">Cargo</label>
                  <input className="field" id="roleTitle" name="roleTitle" />
                </div>
                <div>
                  <label className="label" htmlFor="ct-email">Email</label>
                  <input className="field" id="ct-email" name="email" type="email" />
                </div>
                <div>
                  <label className="label" htmlFor="phone">Teléfono</label>
                  <input className="field" id="phone" name="phone" type="tel" />
                </div>
                <div>
                  <label className="label" htmlFor="source">¿De dónde salió el dato? (obligatorio si hay email o teléfono)</label>
                  <select className="field" id="source" name="source" defaultValue="">
                    <option value="">—</option>
                    {CONTACT_SOURCES.map((s) => (
                      <option key={s} value={s}>
                        {t.contactSources[s]}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label" htmlFor="sourceUrl">URL donde está publicado</label>
                  <input className="field" id="sourceUrl" name="sourceUrl" type="url" placeholder="https://empresa.com/contacto" />
                </div>
                <Submit>Agregar contacto</Submit>
              </ActionForm>
            </details>
          </Card>

          <Card>
            <details>
              <summary className="cursor-pointer text-sm font-semibold text-indigo-700">Editar datos de la empresa</summary>
              <ActionForm action={updateCompanyAction} className="mt-3 space-y-4">
                <input type="hidden" name="companyId" value={c.id} />
                <CompanyFields values={c} />
                <Submit>Guardar cambios</Submit>
              </ActionForm>
            </details>
            {c.notes ? (
              <div className="mt-3 border-t border-slate-100 pt-3">
                <div className="label">Notas internas</div>
                <p className="whitespace-pre-wrap text-sm text-slate-700">{c.notes}</p>
              </div>
            ) : null}
          </Card>
        </div>
      </div>
    </>
  );
}
