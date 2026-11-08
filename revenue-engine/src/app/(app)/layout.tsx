import Link from "next/link";
import { Suspense } from "react";
import { and, count, eq } from "drizzle-orm";
import { getDb } from "@/db";
import { approvals } from "@/db/schema";
import { Nav } from "@/components/nav";
import { t } from "@/i18n";
import { requireUser } from "@/lib/session";
import { areAutomationsPaused } from "@/server/security";
import { logoutAction } from "../(auth)/actions";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  // La sesión se lee al momento del pedido: todo lo que depende de ella va dentro de Suspense.
  return (
    <Suspense fallback={<div className="p-8 text-center text-sm text-slate-500">Cargando…</div>}>
      <AppShell>{children}</AppShell>
    </Suspense>
  );
}

async function AppShell({ children }: { children: React.ReactNode }) {
  const user = await requireUser();

  if (user.role === "client") {
    return (
      <main className="mx-auto max-w-lg p-8 text-center">
        <h1 className="text-xl font-semibold">Portal de clientes</h1>
        <p className="mt-2 text-slate-600">
          El portal privado para empresas clientes se habilita en la Fase 4. Todavía no hay nada para mostrar.
        </p>
        <form action={logoutAction} className="mt-6">
          <button className="btn btn-secondary">{t.nav.salir}</button>
        </form>
      </main>
    );
  }

  const [paused, [pending]] = await Promise.all([
    areAutomationsPaused(user.workspaceId),
    getDb()
      .select({ n: count() })
      .from(approvals)
      .where(and(eq(approvals.workspaceId, user.workspaceId), eq(approvals.status, "pendiente"))),
  ]);

  const items = [
    { href: "/", label: t.nav.panel },
    { href: "/empresas", label: t.nav.empresas },
    { href: "/seguimientos", label: t.nav.seguimientos },
    { href: "/aprobaciones", label: t.nav.aprobaciones, badge: Number(pending.n) },
    { href: "/agentes", label: t.nav.agentes },
    { href: "/seguridad", label: t.nav.seguridad },
  ];

  return (
    <div className="lg:flex">
      <aside className="border-b border-slate-200 bg-slate-100 px-4 py-3 lg:sticky lg:top-0 lg:h-screen lg:w-60 lg:shrink-0 lg:border-b-0 lg:border-r lg:py-6">
        <div className="mb-3 flex items-center justify-between lg:mb-6 lg:block">
          <Link href="/" className="block">
            <div className="text-base font-bold text-slate-900">{t.app.name}</div>
            <div className="text-xs text-slate-500">{user.workspaceName}</div>
          </Link>
          <form action={logoutAction} className="lg:hidden">
            <button className="btn btn-secondary btn-sm">{t.nav.salir}</button>
          </form>
        </div>
        <Nav items={items} />
        <div className="mt-6 hidden border-t border-slate-200 pt-4 text-xs text-slate-600 lg:block">
          <div className="font-semibold text-slate-800">{user.name}</div>
          <div>{t.roles[user.role]}</div>
          <form action={logoutAction} className="mt-3">
            <button className="btn btn-secondary btn-sm">{t.nav.salir}</button>
          </form>
        </div>
      </aside>
      <div className="min-w-0 flex-1">
        {paused ? (
          <div className="bg-red-600 px-4 py-2 text-center text-sm font-semibold text-white">
            Automatizaciones detenidas: ningún agente puede actuar.{" "}
            <Link href="/seguridad" className="underline">
              Ver seguridad
            </Link>
          </div>
        ) : null}
        <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:py-8">{children}</main>
      </div>
    </div>
  );
}
