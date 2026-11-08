/**
 * Portero de acciones.
 *
 * TODA acción que un agente quiera hacer pasa por `requestAction`:
 *  - Nivel 1 → se permite al instante (y queda registrado).
 *  - Nivel 2 → queda en la cola de aprobaciones hasta que alguien del equipo la apruebe.
 *  - Nivel 3 → igual, pero solo el dueño puede aprobarla y tiene que escribir "AUTORIZO".
 * Si las automatizaciones están detenidas, ninguna acción de un agente se permite ni se ejecuta.
 */
import { and, desc, eq } from "drizzle-orm";
import { getDb } from "@/db";
import { approvals } from "@/db/schema";
import { getAgent, isActionType, type ActionType, type ApprovalStatus, type Level } from "@/lib/catalog";
import { writeAudit } from "./audit";
import { assertInternal, type Ctx } from "./context";
import { ForbiddenError, UserError } from "./errors";
import { areAutomationsPaused, getPolicyLevel } from "./security";

export const LEVEL3_CONFIRMATION = "AUTORIZO";

export type Actor = { type: "agent"; agentKey: string } | { type: "user"; userId: string };

export type ActionRequest = {
  workspaceId: string;
  actor: Actor;
  actionType: string;
  summary: string;
  payload?: Record<string, unknown>;
  companyId?: string | null;
  /** Costo estimado en centavos de dólar. Cualquier costo mayor a 0 convierte la acción en Nivel 3. */
  estimatedCostCents?: number;
  isDemo?: boolean;
};

export type ActionOutcome =
  | { outcome: "auto"; level: 1 }
  | { outcome: "pending"; level: 2 | 3; approvalId: string }
  | { outcome: "blocked"; reason: string };

type Executor = (payload: Record<string, unknown>, ctx: Ctx) => Promise<Record<string, unknown>>;

/** Ejecutores reales de acciones (correo, publicaciones, pagos...). Se registran a medida que se conectan integraciones. */
const executors = new Map<ActionType, Executor>();

export function registerExecutor(actionType: ActionType, executor: Executor) {
  executors.set(actionType, executor);
}

export function unregisterExecutor(actionType: ActionType) {
  executors.delete(actionType);
}

function actorFields(actor: Actor) {
  return actor.type === "agent"
    ? { actorType: "agent" as const, actorId: actor.agentKey }
    : { actorType: "user" as const, actorId: actor.userId };
}

export async function requestAction(req: ActionRequest): Promise<ActionOutcome> {
  const { actorType, actorId } = actorFields(req.actor);
  const block = async (reason: string): Promise<ActionOutcome> => {
    await writeAudit({
      workspaceId: req.workspaceId,
      actorType,
      actorId,
      action: "accion.bloqueada",
      entityType: "accion",
      entityId: req.actionType,
      details: { motivo: reason, resumen: req.summary },
    });
    return { outcome: "blocked", reason };
  };

  if (!isActionType(req.actionType)) return block("Tipo de acción desconocido.");
  const actionType = req.actionType;

  if (req.actor.type === "agent") {
    const agent = getAgent(req.actor.agentKey);
    if (!agent) return block("Agente desconocido.");
    if (!agent.actions.includes(actionType)) return block("Este agente no tiene permiso para esta acción.");
    if (await areAutomationsPaused(req.workspaceId)) return block("Las automatizaciones están detenidas.");
  }

  let level: Level = await getPolicyLevel(req.workspaceId, actionType);
  if ((req.estimatedCostCents ?? 0) > 0) level = 3;

  if (level === 1) {
    await writeAudit({
      workspaceId: req.workspaceId,
      actorType,
      actorId,
      action: "accion.automatica",
      entityType: "accion",
      entityId: actionType,
      details: { resumen: req.summary },
    });
    return { outcome: "auto", level: 1 };
  }

  const [row] = await getDb()
    .insert(approvals)
    .values({
      workspaceId: req.workspaceId,
      actionType,
      level,
      summary: req.summary.slice(0, 1000),
      payload: { ...(req.payload ?? {}), costoEstimadoCentavos: req.estimatedCostCents ?? 0 },
      companyId: req.companyId ?? null,
      requestedByType: actorType,
      requestedById: actorId,
      isDemo: req.isDemo ?? false,
    })
    .returning({ id: approvals.id });
  await writeAudit({
    workspaceId: req.workspaceId,
    actorType,
    actorId,
    action: "aprobacion.solicitada",
    entityType: "aprobacion",
    entityId: row.id,
    details: { accion: actionType, nivel: level, resumen: req.summary },
  });
  return { outcome: "pending", level: level as 2 | 3, approvalId: row.id };
}

export type Decision = {
  approvalId: string;
  decision: "aprobar" | "rechazar";
  note?: string | null;
  /** Para el Nivel 3 hay que escribir exactamente "AUTORIZO". */
  confirmation?: string | null;
};

export async function decideApproval(ctx: Ctx, d: Decision) {
  assertInternal(ctx);
  const db = getDb();
  const [current] = await db
    .select()
    .from(approvals)
    .where(and(eq(approvals.id, d.approvalId), eq(approvals.workspaceId, ctx.workspaceId)))
    .limit(1);
  if (!current) throw new UserError("No se encontró la solicitud.");
  if (current.status !== "pendiente") throw new UserError("Esta solicitud ya fue decidida.");

  if (d.decision === "aprobar" && current.level === 3) {
    if (ctx.role !== "owner") throw new ForbiddenError("Las acciones de Nivel 3 solo las puede autorizar el dueño.");
    if ((d.confirmation ?? "").trim().toUpperCase() !== LEVEL3_CONFIRMATION) {
      throw new UserError(`Para autorizar una acción de Nivel 3 escribí ${LEVEL3_CONFIRMATION}.`);
    }
  }

  const newStatus: ApprovalStatus = d.decision === "aprobar" ? "aprobada" : "rechazada";
  // La condición status = 'pendiente' evita que dos personas decidan la misma solicitud a la vez.
  const [updated] = await db
    .update(approvals)
    .set({ status: newStatus, decidedBy: ctx.userId, decidedAt: new Date(), decisionNote: d.note?.trim() || null })
    .where(and(eq(approvals.id, current.id), eq(approvals.status, "pendiente")))
    .returning();
  if (!updated) throw new UserError("Esta solicitud ya fue decidida.");

  await writeAudit({
    workspaceId: ctx.workspaceId,
    actorType: "user",
    actorId: ctx.userId,
    action: d.decision === "aprobar" ? "aprobacion.aprobada" : "aprobacion.rechazada",
    entityType: "aprobacion",
    entityId: current.id,
    details: { accion: current.actionType, nivel: current.level, nota: d.note ?? null },
    ip: ctx.ip,
  });

  if (d.decision === "aprobar") return executeApproved(ctx, current.id);
  return updated;
}

/** Ejecuta una acción ya aprobada, si hay una integración conectada que pueda hacerlo. */
export async function executeApproved(ctx: Ctx, approvalId: string) {
  const db = getDb();
  const [row] = await db
    .select()
    .from(approvals)
    .where(and(eq(approvals.id, approvalId), eq(approvals.workspaceId, ctx.workspaceId)))
    .limit(1);
  if (!row || row.status !== "aprobada") return row;

  const setResult = async (status: ApprovalStatus, result: Record<string, unknown>) => {
    const [u] = await db.update(approvals).set({ status, result }).where(eq(approvals.id, row.id)).returning();
    return u;
  };

  if (await areAutomationsPaused(ctx.workspaceId)) {
    return setResult("aprobada", {
      nota: "Aprobada, pero no se ejecutó porque las automatizaciones están detenidas.",
    });
  }
  const executor = isActionType(row.actionType) ? executors.get(row.actionType) : undefined;
  if (!executor) {
    return setResult("aprobada", {
      nota: "Aprobada. Todavía no hay una integración conectada que pueda ejecutar esta acción: no se realizó nada fuera del sistema.",
    });
  }
  try {
    const result = await executor((row.payload ?? {}) as Record<string, unknown>, ctx);
    await writeAudit({
      workspaceId: ctx.workspaceId,
      actorType: "system",
      action: "aprobacion.ejecutada",
      entityType: "aprobacion",
      entityId: row.id,
      details: { accion: row.actionType },
    });
    return setResult("ejecutada", result);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    await writeAudit({
      workspaceId: ctx.workspaceId,
      actorType: "system",
      action: "aprobacion.fallida",
      entityType: "aprobacion",
      entityId: row.id,
      details: { accion: row.actionType, error: message },
    });
    return setResult("fallida", { error: message });
  }
}

export async function listApprovals(ctx: Ctx, status?: ApprovalStatus) {
  assertInternal(ctx);
  const where = status
    ? and(eq(approvals.workspaceId, ctx.workspaceId), eq(approvals.status, status))
    : eq(approvals.workspaceId, ctx.workspaceId);
  return getDb().select().from(approvals).where(where).orderBy(desc(approvals.createdAt)).limit(200);
}
