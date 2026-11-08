import { redirect } from "next/navigation";
import { ActionForm, Submit } from "@/components/action-form";
import { needsInitialSetup } from "@/server/auth";
import { MIN_PASSWORD_LENGTH } from "@/server/password";
import { setupAction } from "../actions";

export const metadata = { title: "Configuración inicial" };

export default async function SetupPage() {
  if (!(await needsInitialSetup())) redirect("/login");
  return (
    <>
      <h1 className="text-lg font-semibold">Configuración inicial</h1>
      <p className="mb-4 mt-1 text-sm text-slate-600">
        Se hace una sola vez. Vas a crear la cuenta del dueño. El código de instalación es el valor de{" "}
        <code className="rounded bg-slate-100 px-1">SETUP_TOKEN</code> que pusiste en las variables de entorno del
        servidor.
      </p>
      <ActionForm action={setupAction} className="space-y-4">
        <div>
          <label className="label" htmlFor="setupToken">Código de instalación</label>
          <input className="field" id="setupToken" name="setupToken" type="password" required />
        </div>
        <div>
          <label className="label" htmlFor="workspaceName">Nombre de tu negocio</label>
          <input className="field" id="workspaceName" name="workspaceName" defaultValue="Revenue Engine AI" required />
        </div>
        <div>
          <label className="label" htmlFor="name">Tu nombre</label>
          <input className="field" id="name" name="name" autoComplete="name" required />
        </div>
        <div>
          <label className="label" htmlFor="email">Tu email</label>
          <input className="field" id="email" name="email" type="email" autoComplete="email" required />
        </div>
        <div>
          <label className="label" htmlFor="password">Contraseña (mínimo {MIN_PASSWORD_LENGTH} caracteres)</label>
          <input
            className="field"
            id="password"
            name="password"
            type="password"
            minLength={MIN_PASSWORD_LENGTH}
            autoComplete="new-password"
            required
          />
        </div>
        <div>
          <label className="label" htmlFor="password2">Repetir contraseña</label>
          <input
            className="field"
            id="password2"
            name="password2"
            type="password"
            minLength={MIN_PASSWORD_LENGTH}
            autoComplete="new-password"
            required
          />
        </div>
        <Submit>Crear cuenta y entrar</Submit>
      </ActionForm>
    </>
  );
}
