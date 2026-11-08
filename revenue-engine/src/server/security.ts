import { and, desc, eq, lt } from "drizzle-orm";
import { z } from "zod";
import { getDb } from "@/db";
import { actionPolicies, auditLog, suppressionList, workspaces } from "@/db/schema";
import { ACTION_TYPES, isActionType, type ActionType, type Level } from "@/lib/catalog";
import { writeAudit } from "./audit";
import { assertInternal, assertOwner, type Ctx } from "./context";
import { UserError } from "./errors";

// ---------- Espacio de trabajo y botón de parada ----------

export async function getWorkspace(ctx: Ctx) {
  const [ws] = await getDb().select().from(workspaces).where(eq(workspaces.id, ctx.workspaceId)).limit(1);
  if (!ws) throw new UserError("No se encontró el espacio de trabajo.");
  return ws;
}

export async function areAutomationsPaused(workspaceId: string): Promise<boolean> {
  const [ws] = await getDb()
    .select({ paused: workspaces.automationsPaused })
    .from(workspaces)
    .where(eq(workspaces.id, workspaceId))
    .limit(1);
  // Si no se puede leer el estado, por seguridad se considera pausado.
  return ws ? ws.paused : true;
}

/** Cualquier persona del equipo puede DETENER las automatizaciones (es una medida de seguridad). */
export async function pauseAutomations(ctx: Ctx, reason: string) {
  assertInternal(ctx);
  const cleanReason = reason.trim().slice(0, 500) || "Sin motivo indicado";
  await getDb()
    .update(workspaces)
    .set({ automationsPaused: true, pausedAt: new Date(), pausedBy: ctx.userId, pausedReason: cleanReason })
    .where(eq(workspaces.id, ctx.workspaceId));
  await writeAudit({
    workspaceId: ctx.workspaceId,
    actorType: "user",
    actorId: ctx.userId,
    action: "automatizaciones.detenidas",
    details: { motivo: cleanReason },
    ip: ctx.ip,
  });
}

/** Solo el dueño puede volver a encenderlas. */
export async function resumeAutomations(ctx: Ctx) {
  assertOwner(ctx);
  await getDb()
    .update(workspaces)
    .set({ automationsPaused: false, pausedAt: null, pausedBy: null, pausedReason: null })
    .where(eq(workspaces.id, ctx.workspaceId));
  await writeAudit({
    workspaceId: ctx.workspaceId,
    actorType: "user",
    actorId: ctx.userId,
    action: "automatizaciones.reanudadas",
    ip: ctx.ip,
  });
}

const limitsSchema = z.object({
  aiMonthlyBudgetCents: z.number().int().min(0).max(10_000_000),
  maxSpendPerActionCents: z.number().int().min(0).max(10_000_000),
  dailyEmailLimit: z.number().int().min(0).max(500),
});

export async function updateLimits(ctx: Ctx, input: z.input<typeof limitsSchema>) {
  assertOwner(ctx);
  const data = limitsSchema.parse(input);
  const before = await getWorkspace(ctx);
  await getDb().update(workspaces).set(data).where(eq(workspaces.id, ctx.workspaceId));
  await writeAudit({
    workspaceId: ctx.workspaceId,
    actorType: "user",
    actorId: ctx.userId,
    action: "limites.actualizados",
    details: {
      antes: {
        aiMonthlyBudgetCents: before.aiMonthlyBudgetCents,
        maxSpendPerActionCents: before.maxSpendPerActionCents,
        dailyEmailLimit: before.dailyEmailLimit,
      },
      despues: data,
    },
    ip: ctx.ip,
  });
}

// ---------- Niveles de autonomía ----------

export async function getPolicyLevels(workspaceId: string): Promise<Record<ActionType, Level>> {
  const rows = await getDb().select().from(actionPolicies).where(eq(actionPolicies.workspaceId, workspaceId));
  const result = {} as Record<ActionType, Level>;
  for (const [type, def] of Object.entries(ACTION_TYPES) as [ActionType, { minLevel: Level }][]) {
    const row = rows.find((r) => r.actionType === type);
    // Aunque la base de datos dijera otra cosa, nunca se baja del mínimo definido en el código.
    result[type] = Math.max(def.minLevel, row?.level ?? def.minLevel) as Level;
  }
  return result;
}

export async function getPolicyLevel(workspaceId: string, actionType: ActionType): Promise<Level> {
  return (await getPolicyLevels(workspaceId))[actionType];
}

/** Permite SUBIR el nivel de una acción (más control), nunca bajarlo por debajo del mínimo. */
export async function setPolicyLevel(ctx: Ctx, actionType: string, level: number) {
  assertOwner(ctx);
  if (!isActionType(actionType)) throw new UserError("Tipo de acción desconocido.");
  if (![1, 2, 3].includes(level)) throw new UserError("El nivel debe ser 1, 2 o 3.");
  const min = ACTION_TYPES[actionType].minLevel;
  if (level < min) {
    throw new UserError(`Esta acción no puede tener un nivel menor a ${min}.`);
  }
  const before = await getPolicyLevel(ctx.workspaceId, actionType);
  await getDb()
    .insert(actionPolicies)
    .values({ workspaceId: ctx.workspaceId, actionType, level, updatedBy: ctx.userId })
    .onConflictDoUpdate({
      target: [actionPolicies.workspaceId, actionPolicies.actionType],
      set: { level, updatedBy: ctx.userId, updatedAt: new Date() },
    });
  await writeAudit({
    workspaceId: ctx.workspaceId,
    actorType: "user",
    actorId: ctx.userId,
    action: "nivel_autonomia.cambiado",
    entityType: "accion",
    entityId: actionType,
    details: { antes: before, despues: level },
    ip: ctx.ip,
  });
}

// ---------- Lista de exclusión ----------

/** Devuelve el valor normalizado y si es un email o un dominio. */
export function normalizeSuppression(value: string): { value: string; kind: "email" | "dominio" } {
  const v = value.trim().toLowerCase().replace(/^@/, "");
  if (!v) throw new UserError("Escribí un email o un dominio.");
  if (v.includes("@")) {
    if (!z.email().safeParse(v).success) throw new UserError("El email no es válido.");
    return { value: v, kind: "email" };
  }
  if (!/^[a-z0-9-]+(\.[a-z0-9-]+)+$/.test(v)) throw new UserError("El dominio no es válido (ej. empresa.com.uy).");
  return { value: v, kind: "dominio" };
}

export async function addSuppression(ctx: Ctx, rawValue: string, reason?: string | null) {
  assertInternal(ctx);
  const { value, kind } = normalizeSuppression(rawValue);
  await getDb()
    .insert(suppressionList)
    .values({ workspaceId: ctx.workspaceId, value, kind, reason: reason?.trim() || null, createdBy: ctx.userId })
    .onConflictDoNothing();
  await writeAudit({
    workspaceId: ctx.workspaceId,
    actorType: "user",
    actorId: ctx.userId,
    action: "exclusion.agregada",
    entityType: "exclusion",
    entityId: value,
    details: { motivo: reason ?? null },
    ip: ctx.ip,
  });
}

/** Quitar de la lista de exclusión es delicado: solo el dueño, y queda registrado. */
export async function removeSuppression(ctx: Ctx, id: string) {
  assertOwner(ctx);
  const [row] = await getDb()
    .delete(suppressionList)
    .where(and(eq(suppressionList.id, id), eq(suppressionList.workspaceId, ctx.workspaceId)))
    .returning();
  if (row) {
    await writeAudit({
      workspaceId: ctx.workspaceId,
      actorType: "user",
      actorId: ctx.userId,
      action: "exclusion.quitada",
      entityType: "exclusion",
      entityId: row.value,
      ip: ctx.ip,
    });
  }
}

export async function listSuppressions(ctx: Ctx) {
  assertInternal(ctx);
  return getDb()
    .select()
    .from(suppressionList)
    .where(eq(suppressionList.workspaceId, ctx.workspaceId))
    .orderBy(desc(suppressionList.createdAt));
}

/** ¿Este email está bloqueado (por sí mismo o por su dominio)? */
export async function isSuppressed(workspaceId: string, email: string): Promise<boolean> {
  const e = email.trim().toLowerCase();
  const domain = e.split("@")[1] ?? "";
  const rows = await getDb()
    .select({ value: suppressionList.value })
    .from(suppressionList)
    .where(eq(suppressionList.workspaceId, workspaceId));
  return rows.some((r) => r.value === e || (domain && (r.value === domain || domain.endsWith(`.${r.value}`))));
}

// ---------- Registro de actividad ----------

export async function listAudit(ctx: Ctx, opts: { limit?: number; beforeId?: number } = {}) {
  assertInternal(ctx);
  const limit = Math.min(Math.max(opts.limit ?? 100, 1), 500);
  const where = opts.beforeId
    ? and(eq(auditLog.workspaceId, ctx.workspaceId), lt(auditLog.id, opts.beforeId))
    : eq(auditLog.workspaceId, ctx.workspaceId);
  return getDb().select().from(auditLog).where(where).orderBy(desc(auditLog.id)).limit(limit);
}
