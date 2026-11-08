import { redirect } from "next/navigation";
import { ActionForm, Submit } from "@/components/action-form";
import { getCurrentUser } from "@/lib/session";
import { needsInitialSetup } from "@/server/auth";
import { loginAction } from "../actions";

export const metadata = { title: "Iniciar sesión" };

export default async function LoginPage() {
  if (await needsInitialSetup()) redirect("/configuracion-inicial");
  if (await getCurrentUser()) redirect("/");
  return (
    <>
      <h1 className="mb-4 text-lg font-semibold">Iniciar sesión</h1>
      <ActionForm action={loginAction} className="space-y-4">
        <div>
          <label className="label" htmlFor="email">Email</label>
          <input className="field" id="email" name="email" type="email" autoComplete="email" required />
        </div>
        <div>
          <label className="label" htmlFor="password">Contraseña</label>
          <input className="field" id="password" name="password" type="password" autoComplete="current-password" required />
        </div>
        <Submit>Entrar</Submit>
      </ActionForm>
    </>
  );
}
