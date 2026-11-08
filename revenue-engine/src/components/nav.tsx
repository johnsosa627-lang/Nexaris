"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function Nav({ items }: { items: { href: string; label: string; badge?: number }[] }) {
  const pathname = usePathname();
  return (
    <nav className="-mx-1 flex gap-1 overflow-x-auto pb-1 lg:mx-0 lg:flex-col lg:overflow-visible">
      {items.map((it) => {
        const active = it.href === "/" ? pathname === "/" : pathname.startsWith(it.href);
        return (
          <Link
            key={it.href}
            href={it.href}
            className={`flex shrink-0 items-center justify-between gap-2 rounded-lg px-3 py-2 text-sm font-medium ${
              active ? "bg-indigo-600 text-white" : "text-slate-700 hover:bg-slate-200"
            }`}
          >
            <span>{it.label}</span>
            {it.badge ? (
              <span
                className={`rounded-full px-1.5 text-xs font-bold ${active ? "bg-white text-indigo-700" : "bg-amber-500 text-white"}`}
              >
                {it.badge}
              </span>
            ) : null}
          </Link>
        );
      })}
    </nav>
  );
}
