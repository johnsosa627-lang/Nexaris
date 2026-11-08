import { and, eq } from "drizzle-orm";
import { z } from "zod";
import { getDb } from "@/db";
import { agentSettings } from "@/db/schema";
import { AGENTS, AI_MODELS, getAgent } from "@/lib/catalog";
import { diff, writeAudit } from "./audit";
import { assertInternal, assertOwner, type Ctx } from "./context";
import { UserError } from "./errors";

/**
 * Agentes que ya tienen su lógica construida y probada. Un agente solo se puede encender si está acá:
 * así el panel nunca muestra como "activo" algo que en realidad no hace nada.
 * (Etapa 1B: el Director, que coordina los diagnósticos.)
 */
export const RUNNABLE_AGENTS = new Set<string>(["director"]);

export async function listAgents(ctx: Ctx) {
  assertInternal(ctx);
  const rows = await getDb().select().from(agentSettings).where(eq(agentSettings.workspaceId, ctx.workspaceId));
  return AGENTS.map((def) => {
    const s = rows.find((r) => r.agentKey === def.key);
    return {
      ...def,
      runnable: RUNNABLE_AGENTS.has(def.key),
      enabled: (s?.enabled ?? false) && RUNNABLE_AGENTS.has(def.key),
      model: s?.model ?? def.defaultModel,
      monthlyBudgetCents: s?.monthlyBudgetCents ?? 0,
      instructions: s?.instructions ?? "",
    };
  });
}

const settingsSchema = z.object({
  enabled: z.boolean(),
  model: z.enum(AI_MODELS, { message: "Modelo no permitido." }),
  monthlyBudgetCents: z.number().int().min(0, "El presupuesto no puede ser negativo.").max(10_000_000),
  instructions: z
    .string()
    .trim()
    .max(4000, "Las instrucciones son demasiado largas.")
    .transform((v) => v || null),
});

export async function updateAgentSettings(ctx: Ctx, agentKey: string, input: z.input<typeof settingsSchema>) {
  assertOwner(ctx);
  const def = getAgent(agentKey);
  if (!def) throw new UserError("Agente desconocido.");
  const data = settingsSchema.parse(input);
  if (data.enabled && !RUNNABLE_AGENTS.has(agentKey)) {
    throw new UserError(`Este agente todavía no está construido (llega en la Fase ${def.phase}). No se puede encender.`);
  }
  const db = getDb();
  const [before] = await db
    .select()
    .from(agentSettings)
    .where(and(eq(agentSettings.workspaceId, ctx.workspaceId), eq(agentSettings.agentKey, agentKey)))
    .limit(1);
  await db
    .insert(agentSettings)
    .values({ workspaceId: ctx.workspaceId, agentKey, ...data })
    .onConflictDoUpdate({
      target: [agentSettings.workspaceId, agentSettings.agentKey],
      set: { ...data, updatedAt: new Date() },
    });
  const previous = before ?? { enabled: false, model: def.defaultModel, monthlyBudgetCents: 0, instructions: null };
  await writeAudit({
    workspaceId: ctx.workspaceId,
    actorType: "user",
    actorId: ctx.userId,
    action: "agente.configurado",
    entityType: "agente",
    entityId: agentKey,
    details: { cambios: diff(previous as Record<string, unknown>, data) },
    ip: ctx.ip,
  });
}
