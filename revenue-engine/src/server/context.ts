import type { Role } from "@/lib/catalog";
import { ForbiddenError } from "./errors";

/** Quién está haciendo la operación. Toda función del servidor lo recibe y filtra por workspaceId. */
export type Ctx = {
  userId: string;
  workspaceId: string;
  role: Role;
  /** Solo usuarios del portal (rol client): la empresa a la que pertenecen. */
  companyId: string | null;
  ip?: string | null;
};

/** Personas de tu equipo (dueño o equipo). Los usuarios del portal no pasan. */
export function assertInternal(ctx: Ctx): void {
  if (ctx.role !== "owner" && ctx.role !== "team") throw new ForbiddenError();
}

export function assertOwner(ctx: Ctx): void {
  if (ctx.role !== "owner") throw new ForbiddenError("Solo el dueño de la cuenta puede hacer esto.");
}
