"use server";

import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { run, str, type ActionState } from "@/lib/action-state";
import { cookieSecure, getClientIp, getCurrentUser, SESSION_COOKIE } from "@/lib/session";
import { login, logout, setupFirstOwner, toCtx } from "@/server/auth";

async function startSession(email: string, password: string) {
  const ip = await getClientIp();
  const userAgent = (await headers()).get("user-agent");
  const { token, expiresAt } = await login({ email, password }, { ip, userAgent });
  (await cookies()).set(SESSION_COOKIE, token, {
    httpOnly: true,
    secure: cookieSecure(),
    sameSite: "lax",
    path: "/",
    expires: expiresAt,
  });
}

export async function loginAction(_prev: ActionState, form: FormData): Promise<ActionState> {
  const result = await run(() => startSession(str(form, "email"), str(form, "password")));
  if (result?.ok) redirect("/");
  return result;
}

export async function setupAction(_prev: ActionState, form: FormData): Promise<ActionState> {
  const password = str(form, "password");
  if (password !== str(form, "password2")) return { ok: false, message: "Las contraseñas no coinciden." };
  const result = await run(async () => {
    await setupFirstOwner(
      {
        setupToken: str(form, "setupToken"),
        workspaceName: str(form, "workspaceName"),
        name: str(form, "name"),
        email: str(form, "email"),
        password,
      },
      await getClientIp(),
    );
    await startSession(str(form, "email"), password);
  });
  if (result?.ok) redirect("/");
  return result;
}

export async function logoutAction() {
  const store = await cookies();
  const token = store.get(SESSION_COOKIE)?.value;
  const user = await getCurrentUser();
  await logout(token, user ? toCtx(user) : undefined);
  store.delete(SESSION_COOKIE);
  redirect("/login");
}
