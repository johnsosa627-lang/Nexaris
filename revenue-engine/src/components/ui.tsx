import Link from "next/link";
import type { ReactNode } from "react";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">{title}</h1>
        {subtitle ? <p className="mt-1 text-sm text-slate-600">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </div>
  );
}

export function Card({
  title,
  children,
  actions,
  className = "",
  id,
}: {
  title?: ReactNode;
  children: ReactNode;
  actions?: ReactNode;
  className?: string;
  id?: string;
}) {
  return (
    <section id={id} className={`rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5 ${className}`}>
      {title || actions ? (
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          {title ? <h2 className="text-base font-semibold text-slate-900">{title}</h2> : <span />}
          {actions}
        </div>
      ) : null}
      {children}
    </section>
  );
}

export function Stat({
  label,
  value,
  hint,
  href,
  tone = "default",
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  href?: string;
  tone?: "default" | "warning" | "muted";
}) {
  const valueColor = tone === "warning" ? "text-amber-600" : tone === "muted" ? "text-slate-400" : "text-slate-900";
  const body = (
    <div className="h-full rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-indigo-300">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-1 text-2xl font-bold ${valueColor}`}>{value}</div>
      {hint ? <div className="mt-1 text-xs text-slate-500">{hint}</div> : null}
    </div>
  );
  return href ? (
    <Link href={href} className="block h-full">
      {body}
    </Link>
  ) : (
    body
  );
}

const badgeTones = {
  slate: "bg-slate-100 text-slate-700",
  indigo: "bg-indigo-100 text-indigo-800",
  green: "bg-emerald-100 text-emerald-800",
  amber: "bg-amber-100 text-amber-800",
  red: "bg-red-100 text-red-800",
  purple: "bg-purple-100 text-purple-800",
} as const;

export function Badge({ children, tone = "slate" }: { children: ReactNode; tone?: keyof typeof badgeTones }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${badgeTones[tone]}`}>
      {children}
    </span>
  );
}

export function DemoBadge() {
  return <Badge tone="purple">PRUEBA</Badge>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="rounded-lg border border-dashed border-slate-300 p-4 text-center text-sm text-slate-500">{children}</p>;
}

export function stageTone(stage: string): keyof typeof badgeTones {
  if (stage === "cliente") return "green";
  if (stage === "perdido" || stage === "descartado") return "red";
  if (["respondio", "reunion", "propuesta", "negociacion"].includes(stage)) return "amber";
  if (stage === "contactado" || stage === "investigado") return "indigo";
  return "slate";
}

export function levelTone(level: number): keyof typeof badgeTones {
  return level === 3 ? "red" : level === 2 ? "amber" : "green";
}
