import "server-only";
import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";
import { toCtx, validateSessionToken, type SessionUser } from "@/server/auth";
import type { Ctx } from "@/server/context";

export const SESSION_COOKIE = "re_session";

export async function getClientIp(): Promise<string | null> {
  const h = await headers();
  const fwd = h.get("x-forwarded-for");
  return (fwd ? fwd.split(",")[0].trim() : h.get("x-real-ip")) || null;
}

/** Usuario de la sesión actual (se calcula una vez por pedido). */
export const getCurrentUser = cache(async (): Promise<SessionUser | null> => {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  return validateSessionToken(token);
});

/** Para páginas: si no hay sesión, manda al inicio de sesión. */
export async function requireUser(): Promise<SessionUser> {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  return user;
}

/** Para acciones del servidor: devuelve el contexto o corta si no hay sesión. */
export async function requireCtx(): Promise<Ctx> {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  return toCtx(user, await getClientIp());
}

export function cookieSecure(): boolean {
  if (process.env.COOKIE_SECURE) return process.env.COOKIE_SECURE !== "false";
  return process.env.NODE_ENV === "production";
}
