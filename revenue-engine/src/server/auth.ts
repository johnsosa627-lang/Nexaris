import { createHash, randomBytes, timingSafeEqual } from "node:crypto";
import { and, count, eq, gt, lt, sql } from "drizzle-orm";
import { z } from "zod";
import { getDb } from "@/db";
import { auditLog, sessions, users, workspaces } from "@/db/schema";
import type { Role } from "@/lib/catalog";
import { writeAudit } from "./audit";
import type { Ctx } from "./context";
import { UserError } from "./errors";
import { hashPassword, MIN_PASSWORD_LENGTH, verifyPassword } from "./password";

export const SESSION_DAYS = 14;
export const MAX_FAILED_LOGINS = 5;
export const LOCKOUT_MINUTES = 15;

function hashToken(token: string): string {
  return createHash("sha256").update(token).digest("hex");
}

function safeEqual(a: string, b: string): boolean {
  const ba = Buffer.from(a);
  const bb = Buffer.from(b);
  return ba.length === bb.length && timingSafeEqual(ba, bb);
}

const emailSchema = z
  .string()
  .trim()
  .toLowerCase()
  .pipe(z.email({ message: "El email no es válido." }));

const passwordSchema = z
  .string()
  .min(MIN_PASSWORD_LENGTH, `La contraseña debe tener al menos ${MIN_PASSWORD_LENGTH} caracteres.`)
  .max(200, "La contraseña es demasiado larga.");

/** ¿Hay que mostrar la pantalla de configuración inicial? (solo si todavía no existe ningún usuario) */
export async function needsInitialSetup(): Promise<boolean> {
  const [row] = await getDb().select({ n: count() }).from(users);
  return Number(row.n) === 0;
}

const setupSchema = z.object({
  setupToken: z.string().min(1, "Falta el código de instalación."),
  workspaceName: z.string().trim().min(2, "Escribí el nombre de tu negocio.").max(120),
  name: z.string().trim().min(2, "Escribí tu nombre.").max(120),
  email: emailSchema,
  password: passwordSchema,
});

/**
 * Crea el espacio de trabajo y la cuenta del dueño. Solo funciona si no hay ningún usuario
 * y si se escribe el código SETUP_TOKEN configurado en el servidor (así nadie más puede adelantarse).
 */
export async function setupFirstOwner(input: z.input<typeof setupSchema>, ip?: string | null) {
  const data = setupSchema.parse(input);
  const expected = process.env.SETUP_TOKEN;
  if (!expected) {
    throw new UserError("El servidor no tiene configurado SETUP_TOKEN. Agregalo en las variables de entorno.");
  }
  if (!safeEqual(data.setupToken, expected)) {
    await writeAudit({ workspaceId: null, actorType: "anonymous", action: "setup.codigo_incorrecto", ip });
    throw new UserError("El código de instalación no es correcto.");
  }
  const passwordHash = await hashPassword(data.password);
  return getDb().transaction(async (tx) => {
    // Bloqueo para que dos pedidos simultáneos no creen dos dueños.
    await tx.execute(sql`select pg_advisory_xact_lock(424242)`);
    const [existing] = await tx.select({ n: count() }).from(users);
    if (Number(existing.n) > 0) throw new UserError("La instalación ya fue realizada.");
    const [ws] = await tx.insert(workspaces).values({ name: data.workspaceName }).returning();
    const [user] = await tx
      .insert(users)
      .values({
        workspaceId: ws.id,
        email: data.email,
        name: data.name,
        passwordHash,
        role: "owner",
      })
      .returning();
    await tx.insert(auditLog).values({
      workspaceId: ws.id,
      actorType: "user",
      actorId: user.id,
      action: "setup.completado",
      entityType: "workspace",
      entityId: ws.id,
      ip: ip ?? null,
    });
    return { workspaceId: ws.id, userId: user.id };
  });
}

async function recentFailedLogins(email: string): Promise<number> {
  const since = new Date(Date.now() - LOCKOUT_MINUTES * 60_000);
  const [row] = await getDb()
    .select({ n: count() })
    .from(auditLog)
    .where(and(eq(auditLog.action, "login.fallido"), eq(auditLog.entityId, email), gt(auditLog.at, since)));
  return Number(row.n);
}

export type LoginResult = { token: string; expiresAt: Date };

export async function login(
  input: { email: string; password: string },
  meta: { ip?: string | null; userAgent?: string | null } = {},
): Promise<LoginResult> {
  const parsedEmail = emailSchema.safeParse(input.email);
  const generic = new UserError("Email o contraseña incorrectos.");
  if (!parsedEmail.success || !input.password) throw generic;
  const email = parsedEmail.data;

  if ((await recentFailedLogins(email)) >= MAX_FAILED_LOGINS) {
    throw new UserError(
      `Demasiados intentos fallidos. Esperá ${LOCKOUT_MINUTES} minutos antes de volver a intentar.`,
    );
  }

  const db = getDb();
  const [user] = await db.select().from(users).where(eq(users.email, email)).limit(1);
  const ok = user && user.active && (await verifyPassword(input.password, user.passwordHash));
  if (!ok) {
    await writeAudit({
      workspaceId: user?.workspaceId ?? null,
      actorType: "anonymous",
      action: "login.fallido",
      entityType: "email",
      entityId: email,
      ip: meta.ip,
    });
    throw generic;
  }

  const token = randomBytes(32).toString("base64url");
  const expiresAt = new Date(Date.now() + SESSION_DAYS * 24 * 3600_000);
  await db.insert(sessions).values({
    id: hashToken(token),
    userId: user.id,
    expiresAt,
    ip: meta.ip ?? null,
    userAgent: meta.userAgent?.slice(0, 300) ?? null,
  });
  await db.update(users).set({ lastLoginAt: new Date() }).where(eq(users.id, user.id));
  // Limpieza de sesiones vencidas (barata, aprovecha el inicio de sesión).
  await db.delete(sessions).where(lt(sessions.expiresAt, new Date()));
  await writeAudit({
    workspaceId: user.workspaceId,
    actorType: "user",
    actorId: user.id,
    action: "login.correcto",
    ip: meta.ip,
  });
  return { token, expiresAt };
}

export type SessionUser = {
  id: string;
  name: string;
  email: string;
  role: Role;
  workspaceId: string;
  companyId: string | null;
  workspaceName: string;
};

export async function validateSessionToken(token: string | undefined | null): Promise<SessionUser | null> {
  if (!token) return null;
  const [row] = await getDb()
    .select({
      id: users.id,
      name: users.name,
      email: users.email,
      role: users.role,
      workspaceId: users.workspaceId,
      companyId: users.companyId,
      active: users.active,
      workspaceName: workspaces.name,
      expiresAt: sessions.expiresAt,
    })
    .from(sessions)
    .innerJoin(users, eq(users.id, sessions.userId))
    .innerJoin(workspaces, eq(workspaces.id, users.workspaceId))
    .where(eq(sessions.id, hashToken(token)))
    .limit(1);
  if (!row || !row.active || row.expiresAt < new Date()) return null;
  return {
    id: row.id,
    name: row.name,
    email: row.email,
    role: row.role as Role,
    workspaceId: row.workspaceId,
    companyId: row.companyId,
    workspaceName: row.workspaceName,
  };
}

export async function logout(token: string | undefined | null, ctx?: Ctx): Promise<void> {
  if (!token) return;
  await getDb().delete(sessions).where(eq(sessions.id, hashToken(token)));
  if (ctx) {
    await writeAudit({ workspaceId: ctx.workspaceId, actorType: "user", actorId: ctx.userId, action: "logout" });
  }
}

export function toCtx(user: SessionUser, ip?: string | null): Ctx {
  return { userId: user.id, workspaceId: user.workspaceId, role: user.role, companyId: user.companyId, ip };
}
