import { ActionForm, Submit } from "@/components/action-form";
import { AutoRefresh } from "@/components/auto-refresh";
import { Badge, Card } from "@/components/ui";
import type { findings as findingsTable, diagnoses as diagnosesTable } from "@/db/schema";
import { formatDateTime, formatMoney } from "@/lib/format";
import type { AiSummary } from "@/server/analyzer/ai";
import type { ScoreResult, SiteFacts } from "@/server/analyzer/types";
import { addFoundEmailAction, requestDiagnosisAction } from "@/app/(app)/empresas/actions";

type Diagnosis = typeof diagnosesTable.$inferSelect;
type FindingRow = typeof findingsTable.$inferSelect;

const SEVERITY: Record<string, { label: string; tone: "red" | "amber" | "indigo" | "slate" }> = {
  critica: { label: "Crítico", tone: "red" },
  alta: { label: "Alto", tone: "red" },
  media: { label: "Medio", tone: "amber" },
  baja: { label: "Bajo", tone: "slate" },
  info: { label: "Dato", tone: "indigo" },
};
const SEVERITY_ORDER = ["critica", "alta", "media", "baja", "info"];
const GROUP_LABELS = { necesidad: "Necesidad", inversion: "Capacidad de inversión", contacto: "Contactabilidad" } as const;

export function scoreTone(score: number | null | undefined): "green" | "amber" | "slate" {
  if (score == null) return "slate";
  return score >= 60 ? "green" : score >= 35 ? "amber" : "slate";
}

export function DiagnosisCard({
  companyId,
  hasWebsite,
  latest,
  findings,
  pending,
  history,
  existingEmails,
}: {
  companyId: string;
  hasWebsite: boolean;
  latest: Diagnosis | null;
  findings: FindingRow[];
  pending: Diagnosis | null;
  history: Diagnosis[];
  existingEmails: string[];
}) {
  const facts = latest?.facts as SiteFacts | null | undefined;
  const score = latest?.scoreBreakdown as ScoreResult | null | undefined;
  const ai = latest?.aiSummary as AiSummary | null | undefined;
  const byCode = new Map(findings.map((f) => [f.code, f]));
  const sorted = [...findings].sort((a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity));
  const lastFailed = history[0]?.status === "fallido" ? history[0] : null;
  const foundEmails = (facts?.contact.emails ?? []).filter((e) => !existingEmails.includes(e.email));

  return (
    <Card
      title="Diagnóstico"
      actions={
        hasWebsite && !pending ? (
          <ActionForm action={requestDiagnosisAction}>
            <input type="hidden" name="companyId" value={companyId} />
            <Submit size="sm" variant={latest ? "secondary" : "primary"}>
              {latest ? "Volver a analizar" : "Analizar sitio web"}
            </Submit>
          </ActionForm>
        ) : null
      }
    >
      {pending ? (
        <div className="mb-3 rounded-lg border border-indigo-200 bg-indigo-50 p-3 text-sm text-indigo-900">
          <AutoRefresh />
          {pending.status === "en_proceso" ? "Analizando el sitio…" : "En cola para analizar…"} Esta sección se actualiza sola.
        </div>
      ) : null}

      {!hasWebsite ? <p className="text-sm text-slate-500">Cargá el sitio web de la empresa para poder analizarla.</p> : null}
      {lastFailed && !pending ? (
        <p className="mb-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          El último análisis falló: {lastFailed.error}
        </p>
      ) : null}
      {!latest && hasWebsite && !pending ? (
        <p className="text-sm text-slate-500">
          Todavía no se analizó. El análisis revisa la página principal (velocidad, celular, Google, medición, publicidad y
          contacto) y, si hay clave de IA, redacta un resumen comercial.
        </p>
      ) : null}

      {latest && score ? (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-4">
            <div className="text-center">
              <div className="text-4xl font-bold text-slate-900">{latest.score}</div>
              <div className="text-xs text-slate-500">de 100</div>
            </div>
            <div className="min-w-0 flex-1 space-y-1">
              {(Object.keys(GROUP_LABELS) as (keyof typeof GROUP_LABELS)[]).map((g) => (
                <div key={g} className="text-xs">
                  <div className="flex justify-between text-slate-600">
                    <span>{GROUP_LABELS[g]}</span>
                    <span>
                      {score.groups[g].points}/{score.groups[g].max}
                    </span>
                  </div>
                  <div className="h-1.5 rounded bg-slate-100">
                    <div className="h-1.5 rounded bg-indigo-500" style={{ width: `${(score.groups[g].points / score.groups[g].max) * 100}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
          <details className="text-xs text-slate-600">
            <summary className="cursor-pointer">¿Cómo se calcula la puntuación?</summary>
            <p className="mt-1">
              Prioriza a quién contactar: suma problemas solucionables (necesidad), señales de que ya invierte en lo digital y
              qué tan fácil es contactarla. No predice ventas.
            </p>
            <ul className="mt-1 list-disc pl-4">
              {score.items.map((it, i) => (
                <li key={i}>
                  {GROUP_LABELS[it.group]}: {it.label} (+{it.points})
                </li>
              ))}
            </ul>
          </details>

          {ai ? (
            <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <Badge tone="indigo">Resumen redactado por IA</Badge>
                <span>basado solo en los hechos medidos</span>
              </div>
              <p className="text-sm text-slate-800">{ai.resumen}</p>
              {ai.problemas.length ? (
                <div>
                  <div className="label">Problemas principales</div>
                  <ul className="space-y-2">
                    {ai.problemas.map((p, i) => (
                      <li key={i} className="text-sm">
                        <div className="flex flex-wrap items-center gap-2 font-medium">
                          <Badge tone={p.prioridad === "alta" ? "red" : p.prioridad === "media" ? "amber" : "slate"}>{p.prioridad}</Badge>
                          {p.titulo}
                        </div>
                        <p className="text-slate-700">{p.explicacion}</p>
                        <p className="text-xs text-slate-500">
                          Respaldo: {p.codigos.map((c) => byCode.get(c)?.title ?? c).join(" · ")}
                        </p>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {ai.servicios.length ? (
                <div>
                  <div className="label">Servicios que podrían ayudar</div>
                  <ul className="list-disc space-y-1 pl-5 text-sm">
                    {ai.servicios.map((s, i) => (
                      <li key={i}>
                        <strong>{s.servicio}:</strong> {s.motivo}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {ai.estimaciones.length ? (
                <div>
                  <div className="label">Estimaciones (no comprobadas)</div>
                  <ul className="space-y-1 text-sm">
                    {ai.estimaciones.map((e, i) => (
                      <li key={i}>
                        <Badge tone="amber">Estimación</Badge> {e.texto} <span className="text-xs text-slate-500">(se apoya en: {e.base})</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {ai.preguntas.length ? (
                <div>
                  <div className="label">Preguntas para hacerle a la empresa</div>
                  <ul className="list-disc pl-5 text-sm">
                    {ai.preguntas.map((q, i) => (
                      <li key={i}>{q}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {ai.limitaciones.length ? (
                <p className="text-xs text-slate-500">Limitaciones: {ai.limitaciones.join(" · ")}</p>
              ) : null}
            </div>
          ) : null}
          {latest.aiNote ? <p className="text-xs text-amber-800">{latest.aiNote}</p> : null}

          <div>
            <div className="label">
              Hallazgos comprobados ({sorted.filter((f) => f.severity !== "info").length} problema(s)
              {sorted.some((f) => f.severity === "info") ? ` + ${sorted.filter((f) => f.severity === "info").length} dato(s)` : ""})
            </div>
            {sorted.length === 0 ? (
              <p className="text-sm text-slate-500">No se encontraron problemas en la página principal.</p>
            ) : (
              <ul className="space-y-2">
                {sorted.map((f) => (
                  <li key={f.id} className="rounded-lg border border-slate-200 p-2 text-sm">
                    <div className="flex flex-wrap items-center gap-2 font-medium">
                      <Badge tone={SEVERITY[f.severity]?.tone ?? "slate"}>{SEVERITY[f.severity]?.label ?? f.severity}</Badge>
                      <Badge tone="green">Hecho</Badge>
                      {f.title}
                    </div>
                    <p className="mt-0.5 text-slate-700">{f.detail}</p>
                    {f.evidence ? <p className="mt-0.5 break-all text-xs text-slate-500">Evidencia: {f.evidence}</p> : null}
                    {f.recommendation ? <p className="mt-0.5 text-xs text-slate-600">Qué hacer: {f.recommendation}</p> : null}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {foundEmails.length ? (
            <div>
              <div className="label">Emails publicados en el sitio</div>
              <ul className="space-y-1">
                {foundEmails.map((e) => (
                  <li key={e.email} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                    <span className="break-all">
                      {e.email} {e.sameDomain ? null : <Badge tone="amber">otro dominio</Badge>}
                    </span>
                    <ActionForm action={addFoundEmailAction}>
                      <input type="hidden" name="companyId" value={companyId} />
                      <input type="hidden" name="email" value={e.email} />
                      <input type="hidden" name="sourceUrl" value={latest.analyzedUrl ?? ""} />
                      <Submit size="sm" variant="secondary">
                        Agregar como contacto
                      </Submit>
                    </ActionForm>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <p className="text-xs text-slate-500">
            Analizado {formatDateTime(latest.finishedAt)} · {latest.analyzedUrl}
            {facts?.pagespeed == null ? " · Sin PageSpeed (falta PAGESPEED_API_KEY)" : facts.pagespeed.ok ? "" : ` · ${facts.pagespeed.error}`}
            {latest.model ? ` · IA: ${latest.model}, costo ${formatMoney(latest.costCents)}` : ""}
          </p>
        </div>
      ) : null}

      {history.length > 1 ? (
        <details className="mt-3 text-xs text-slate-600">
          <summary className="cursor-pointer">Análisis anteriores ({history.length})</summary>
          <ul className="mt-1 space-y-0.5">
            {history.map((h) => (
              <li key={h.id}>
                {formatDateTime(h.createdAt)} · {h.status}
                {h.score != null ? ` · ${h.score}/100` : ""}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </Card>
  );
}
