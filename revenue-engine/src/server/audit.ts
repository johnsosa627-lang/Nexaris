import { getDb } from "@/db";
import { auditLog } from "@/db/schema";

export type AuditEntry = {
  workspaceId: string | null;
  actorType: "user" | "agent" | "system" | "anonymous";
  actorId?: string | null;
  action: string;
  entityType?: string | null;
  entityId?: string | null;
  details?: Record<string, unknown> | null;
  ip?: string | null;
};

/** Agrega una fila al registro de actividad. No existe ninguna función para editarlo o borrarlo. */
export async function writeAudit(entry: AuditEntry): Promise<void> {
  await getDb()
    .insert(auditLog)
    .values({
      workspaceId: entry.workspaceId,
      actorType: entry.actorType,
      actorId: entry.actorId ?? null,
      action: entry.action,
      entityType: entry.entityType ?? null,
      entityId: entry.entityId ?? null,
      details: entry.details ?? null,
      ip: entry.ip ?? null,
    });
}

/** Devuelve solo los campos que cambiaron, para guardar el historial de cambios. */
export function diff<T extends Record<string, unknown>>(
  before: T,
  after: Partial<T>,
): Record<string, { antes: unknown; despues: unknown }> {
  const changes: Record<string, { antes: unknown; despues: unknown }> = {};
  for (const key of Object.keys(after)) {
    const a = before[key] ?? null;
    const b = after[key] ?? null;
    if (JSON.stringify(a) !== JSON.stringify(b)) changes[key] = { antes: a, despues: b };
  }
  return changes;
}
