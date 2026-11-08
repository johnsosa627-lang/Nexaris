/**
 * Diagnósticos de empresas: cola, ejecución y consulta.
 *
 * Flujo: pedir diagnóstico → pasa por el portero de acciones (agente Director, "preparar_diagnostico")
 * → queda "en_cola" → el trabajador en segundo plano lo toma → analiza el sitio → (si hay clave y presupuesto)
 * Claude redacta el resumen → se guardan hechos, hallazgos, puntuación y costo.
 */
import { and, asc, desc, eq, gte, inArray, isNotNull, lt, notExists, sql } from "drizzle-orm";
import { z } from "zod";
import { getDb } from "@/db";
import { activities, agentSettings, aiUsage, companies, diagnoses, findings, workspaces } from "@/db/schema";
import { getAgent, type AiModel } from "@/lib/catalog";
import { analyzeSite } from "./analyzer";
import { buildPrompt, summarizeWithClaude, worstCaseMillicents, type ClaudeClient } from "./analyzer/ai";
import { writeAudit } from "./audit";
import { assertInternal, type Ctx } from "./context";
import { UserError } from "./errors";
import { registerExecutor, requestAction } from "./gateway";

const DIRECTOR = "director";
export const MAX_ATTEMPTS = 3;
export const STALE_MINUTES = 10;

async function directorSettings(workspaceId: string) {
  const [s] = await getDb()
    .select()
    .from(agentSettings)
    .where(and(eq(agentSettings.workspaceId, workspaceId), eq(agentSettings.agentKey, DIRECTOR)))
    .limit(1);
  const def = getAgent(DIRECTOR)!;
  return {
    enabled: s?.enabled ?? false,
    model: (s?.model ?? def.defaultModel) as AiModel,
    monthlyBudgetCents: s?.monthlyBudgetCents ?? 0,
    instructions: s?.instructions ?? null,
  };
}

/** Inicio del mes actual en Montevideo (UTC-3). */
export function monthStart(now = new Date()): Date {
  const local = new Date(now.getTime() - 3 * 3600_000);
  return new Date(Date.UTC(local.getUTCFullYear(), local.getUTCMonth(), 1, 3, 0, 0));
}

/** Gasto de IA del mes, en milicentavos (1 = US$0,00001). */
export async function aiSpendThisMonth(workspaceId: string, agentKey?: string): Promise<number> {
  const conds = [eq(aiUsage.workspaceId, workspaceId), gte(aiUsage.createdAt, monthStart())];
  if (agentKey) conds.push(eq(aiUsage.agentKey, agentKey));
  const [row] = await getDb()
    .select({ total: sql<string>`coalesce(sum(${aiUsage.costMillicents}), 0)` })
    .from(aiUsage)
    .where(and(...conds));
  return Number(row.total);
}

// ---------- Pedir diagnósticos ----------

async function enqueue(workspaceId: string, companyId: string, userId: string | null, isDemo: boolean) {
  const db = getDb();
  const [busy] = await db
    .select({ id: diagnoses.id })
    .from(diagnoses)
    .where(and(eq(diagnoses.companyId, companyId), inArray(diagnoses.status, ["en_cola", "en_proceso"])))
    .limit(1);
  if (busy) return { id: busy.id, alreadyQueued: true };
  const [row] = await db
    .insert(diagnoses)
    .values({ workspaceId, companyId, requestedBy: userId, isDemo })
    .returning({ id: diagnoses.id });
  return { id: row.id, alreadyQueued: false };
}

export type DiagnosisRequestResult =
  | { status: "en_cola"; diagnosisId: string; alreadyQueued: boolean }
  | { status: "requiere_aprobacion"; approvalId: string };

export async function requestDiagnosis(ctx: Ctx, companyId: string): Promise<DiagnosisRequestResult> {
  assertInternal(ctx);
  if (!z.uuid().safeParse(companyId).success) throw new UserError("Empresa no encontrada.");
  const [company] = await getDb()
    .select()
    .from(companies)
    .where(and(eq(companies.id, companyId), eq(companies.workspaceId, ctx.workspaceId)))
    .limit(1);
  if (!company) throw new UserError("Empresa no encontrada.");
  if (!company.website) throw new UserError("Cargá el sitio web de la empresa antes de analizarla.");

  const director = await directorSettings(ctx.workspaceId);
  if (!director.enabled) {
    throw new UserError("El Director General está apagado. Encendelo en «Agentes» para poder hacer diagnósticos.");
  }

  const outcome = await requestAction({
    workspaceId: ctx.workspaceId,
    actor: { type: "agent", agentKey: DIRECTOR },
    actionType: "preparar_diagnostico",
    summary: `Analizar el sitio de ${company.name} (${company.domain})`,
    payload: { companyId, requestedBy: ctx.userId },
    companyId,
    isDemo: company.isDemo,
  });
  if (outcome.outcome === "blocked") throw new UserError(`No se puede analizar: ${outcome.reason}`);
  if (outcome.outcome === "pending") return { status: "requiere_aprobacion", approvalId: outcome.approvalId };

  const q = await enqueue(ctx.workspaceId, companyId, ctx.userId, company.isDemo);
  if (!q.alreadyQueued) {
    await writeAudit({
      workspaceId: ctx.workspaceId,
      actorType: "user",
      actorId: ctx.userId,
      action: "diagnostico.pedido",
      entityType: "empresa",
      entityId: companyId,
      ip: ctx.ip,
    });
  }
  return { status: "en_cola", diagnosisId: q.id, alreadyQueued: q.alreadyQueued };
}

// Si alguien sube "preparar_diagnostico" a Nivel 2, al aprobarse se encola desde acá.
registerExecutor("preparar_diagnostico", async (payload, ctx) => {
  const companyId = String(payload.companyId ?? "");
  const [company] = await getDb()
    .select({ id: companies.id, isDemo: companies.isDemo })
    .from(companies)
    .where(and(eq(companies.id, companyId), eq(companies.workspaceId, ctx.workspaceId)))
    .limit(1);
  if (!company) throw new Error("La empresa ya no existe.");
  const q = await enqueue(ctx.workspaceId, companyId, ctx.userId, company.isDemo);
  return { nota: "Diagnóstico puesto en cola.", diagnosticoId: q.id };
});

/** Encola el análisis de las empresas con sitio web que todavía no tienen diagnóstico. */
export async function requestPendingDiagnoses(ctx: Ctx, max = 25) {
  assertInternal(ctx);
  const db = getDb();
  const rows = await db
    .select({ id: companies.id })
    .from(companies)
    .where(
      and(
        eq(companies.workspaceId, ctx.workspaceId),
        isNotNull(companies.website),
        notExists(db.select({ x: sql`1` }).from(diagnoses).where(eq(diagnoses.companyId, companies.id))),
      ),
    )
    .orderBy(asc(companies.createdAt))
    .limit(max);
  let queued = 0;
  let approvals = 0;
  for (const r of rows) {
    const res = await requestDiagnosis(ctx, r.id);
    if (res.status === "en_cola" && !res.alreadyQueued) queued++;
    if (res.status === "requiere_aprobacion") approvals++;
  }
  return { queued, approvals, found: rows.length };
}

// ---------- Ejecutar ----------

/** Toma el siguiente diagnóstico de la cola (si las automatizaciones no están detenidas). */
async function claimNext() {
  const result = await getDb().execute(sql`
    update ${diagnoses} set status = 'en_proceso', started_at = now(), attempts = attempts + 1
    where id = (
      select d.id from ${diagnoses} d
      join ${workspaces} w on w.id = d.workspace_id
      where d.status = 'en_cola' and w.automations_paused = false
      order by d.created_at
      for update of d skip locked
      limit 1
    )
    returning id
  `);
  const rows = result as unknown as { id: string }[];
  return rows[0]?.id ?? null;
}

/** Devuelve a la cola los análisis que quedaron colgados (por ejemplo, si se reinició el servidor). */
export async function recoverStale() {
  const limit = new Date(Date.now() - STALE_MINUTES * 60_000);
  const db = getDb();
  await db
    .update(diagnoses)
    .set({ status: "fallido", error: "No terminó después de varios intentos.", finishedAt: new Date() })
    .where(and(eq(diagnoses.status, "en_proceso"), lt(diagnoses.startedAt, limit), gte(diagnoses.attempts, MAX_ATTEMPTS)));
  await db
    .update(diagnoses)
    .set({ status: "en_cola" })
    .where(and(eq(diagnoses.status, "en_proceso"), lt(diagnoses.startedAt, limit)));
}

export type RunOptions = { claude?: ClaudeClient; now?: Date };

export async function runDiagnosis(id: string, opts: RunOptions = {}) {
  const db = getDb();
  const [d] = await db.select().from(diagnoses).where(eq(diagnoses.id, id)).limit(1);
  if (!d) return;
  const [company] = await db.select().from(companies).where(eq(companies.id, d.companyId)).limit(1);
  try {
    if (!company?.website) throw new Error("La empresa ya no tiene sitio web cargado.");
    const analysis = await analyzeSite(company.website, { now: opts.now });

    // Resumen con IA, solo si hay presupuesto
    const director = await directorSettings(d.workspaceId);
    const [ws] = await db.select().from(workspaces).where(eq(workspaces.id, d.workspaceId)).limit(1);
    let aiSummary: unknown = null;
    let aiNote: string | null = null;
    let model: string | null = null;
    let cost = 0;

    const canSummarize = analysis.facts.robotsAllowed && !analysis.facts.error;
    if (!canSummarize) {
      aiNote = "No se pidió resumen a la IA porque el sitio no se pudo analizar.";
    } else {
      const prompt = buildPrompt({
        companyName: company.name,
        sector: company.sector,
        city: company.city,
        country: company.country,
        facts: analysis.facts,
        findings: analysis.findings,
        score: analysis.score,
        extraInstructions: director.instructions,
      });
      const worst = worstCaseMillicents(director.model, prompt.length);
      const wsSpent = await aiSpendThisMonth(d.workspaceId);
      const agentSpent = await aiSpendThisMonth(d.workspaceId, DIRECTOR);
      const wsLimit = (ws?.aiMonthlyBudgetCents ?? 0) * 1000;
      const agentLimit = director.monthlyBudgetCents * 1000;
      if (wsSpent + worst > wsLimit) {
        aiNote = "Se alcanzó el tope mensual de gasto en IA (Seguridad → Límites). El diagnóstico se guardó sin resumen.";
      } else if (agentLimit > 0 && agentSpent + worst > agentLimit) {
        aiNote = "Se alcanzó el presupuesto mensual del Director (Agentes). El diagnóstico se guardó sin resumen.";
      } else {
        const ai = await summarizeWithClaude(prompt, analysis.findings, director.model, opts.claude);
        if (ai.inputTokens || ai.outputTokens) {
          await db.insert(aiUsage).values({
            workspaceId: d.workspaceId,
            agentKey: DIRECTOR,
            model: ai.model ?? director.model,
            purpose: "diagnostico",
            inputTokens: ai.inputTokens ?? 0,
            outputTokens: ai.outputTokens ?? 0,
            costMillicents: ai.costMillicents ?? 0,
            diagnosisId: d.id,
          });
          cost = ai.costMillicents ?? 0;
          model = ai.model ?? director.model;
        }
        if (ai.ok) {
          aiSummary = ai.summary;
          if (ai.discarded > 0) aiNote = `Se descartaron ${ai.discarded} punto(s) de la IA que no estaban respaldados por hallazgos.`;
        } else {
          aiNote = ai.note;
        }
      }
    }

    await db.transaction(async (tx) => {
      await tx
        .update(diagnoses)
        .set({
          status: "listo",
          analyzedUrl: analysis.facts.finalUrl ?? analysis.facts.requestedUrl,
          facts: analysis.facts,
          score: analysis.score.score,
          scoreBreakdown: analysis.score,
          aiSummary,
          aiNote,
          model,
          costCents: Math.ceil(cost / 1000),
          error: null,
          finishedAt: new Date(),
        })
        .where(eq(diagnoses.id, d.id));
      if (analysis.findings.length) {
        await tx.insert(findings).values(
          analysis.findings.map((f) => ({ ...f, workspaceId: d.workspaceId, diagnosisId: d.id, companyId: d.companyId })),
        );
      }
      await tx
        .update(companies)
        .set({
          opportunityScore: analysis.score.score,
          stage: company.stage === "nuevo" ? "investigado" : company.stage,
          updatedAt: new Date(),
        })
        .where(eq(companies.id, company.id));
      await tx.insert(activities).values({
        workspaceId: d.workspaceId,
        companyId: company.id,
        type: "sistema",
        title: `Diagnóstico listo: puntuación ${analysis.score.score}/100, ${analysis.findings.filter((f) => f.severity !== "info").length} problema(s) detectado(s)`,
        actorType: "agent",
        actorId: DIRECTOR,
        isDemo: d.isDemo,
      });
    });
    await writeAudit({
      workspaceId: d.workspaceId,
      actorType: "agent",
      actorId: DIRECTOR,
      action: "diagnostico.listo",
      entityType: "empresa",
      entityId: company.id,
      details: { puntuacion: analysis.score.score, costoMilicentavos: cost, modelo: model, notaIA: aiNote },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    await db
      .update(diagnoses)
      .set({ status: "fallido", error: message, finishedAt: new Date() })
      .where(eq(diagnoses.id, d.id));
    await writeAudit({
      workspaceId: d.workspaceId,
      actorType: "agent",
      actorId: DIRECTOR,
      action: "diagnostico.fallido",
      entityType: "empresa",
      entityId: d.companyId,
      details: { error: message },
    });
  }
}

/** Procesa la cola hasta vaciarla (de a uno). Devuelve cuántos procesó. */
export async function processQueue(opts: RunOptions = {}): Promise<number> {
  let n = 0;
  while (true) {
    const id = await claimNext();
    if (!id) return n;
    await runDiagnosis(id, opts);
    n++;
  }
}

// ---------- Consultar ----------

export async function getDiagnoses(ctx: Ctx, companyId: string) {
  assertInternal(ctx);
  const db = getDb();
  const list = await db
    .select()
    .from(diagnoses)
    .where(and(eq(diagnoses.companyId, companyId), eq(diagnoses.workspaceId, ctx.workspaceId)))
    .orderBy(desc(diagnoses.createdAt))
    .limit(20);
  const latestDone = list.find((d) => d.status === "listo") ?? null;
  const latestFindings = latestDone
    ? await db.select().from(findings).where(eq(findings.diagnosisId, latestDone.id)).orderBy(asc(findings.createdAt))
    : [];
  const pending = list.find((d) => d.status === "en_cola" || d.status === "en_proceso") ?? null;
  return { list, latestDone, latestFindings, pending };
}

export async function getAiSpendSummary(ctx: Ctx) {
  assertInternal(ctx);
  const [ws] = await getDb().select().from(workspaces).where(eq(workspaces.id, ctx.workspaceId)).limit(1);
  const spent = await aiSpendThisMonth(ctx.workspaceId);
  return { spentCents: spent / 1000, budgetCents: ws?.aiMonthlyBudgetCents ?? 0 };
}
