import { Suspense } from "react";
import { t } from "@/i18n";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <div className="text-2xl font-bold text-slate-900">{t.app.name}</div>
          <div className="mt-1 text-sm text-slate-600">{t.app.tagline}</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <Suspense fallback={<p className="text-sm text-slate-500">Cargando…</p>}>{children}</Suspense>
        </div>
      </div>
    </main>
  );
}
