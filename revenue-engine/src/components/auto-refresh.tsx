"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

/** Mientras está en pantalla, vuelve a pedir los datos cada pocos segundos (para ver un análisis en curso). */
export function AutoRefresh({ everyMs = 4000 }: { everyMs?: number }) {
  const router = useRouter();
  useEffect(() => {
    const t = setInterval(() => router.refresh(), everyMs);
    return () => clearInterval(t);
  }, [router, everyMs]);
  return null;
}
