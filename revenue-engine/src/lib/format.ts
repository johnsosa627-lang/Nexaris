/** Formatos de fecha y dinero. El dinero se guarda siempre en centavos (enteros) + moneda. */
const TZ = "America/Montevideo";

export function formatDate(value: Date | string | null | undefined, locale = "es-UY"): string {
  if (!value) return "—";
  const d = typeof value === "string" ? new Date(value) : value;
  return d.toLocaleDateString(locale, { timeZone: TZ, day: "2-digit", month: "2-digit", year: "numeric" });
}

export function formatDateTime(value: Date | string | null | undefined, locale = "es-UY"): string {
  if (!value) return "—";
  const d = typeof value === "string" ? new Date(value) : value;
  return d.toLocaleString(locale, {
    timeZone: TZ,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatMoney(cents: number, currency = "USD", locale = "es-UY"): string {
  return new Intl.NumberFormat(locale, { style: "currency", currency }).format(cents / 100);
}

/** Normaliza una URL a su dominio, sin "www." (ej. "https://www.Ejemplo.com.uy/x" → "ejemplo.com.uy"). */
export function domainFromUrl(input: string | null | undefined): string | null {
  if (!input) return null;
  const raw = input.trim();
  if (!raw) return null;
  try {
    const url = new URL(/^https?:\/\//i.test(raw) ? raw : `https://${raw}`);
    const host = url.hostname.toLowerCase().replace(/^www\./, "");
    if (!host.includes(".")) return null;
    return host;
  } catch {
    return null;
  }
}

/** Devuelve una URL con https:// si el usuario la escribió sin esquema. */
export function normalizeWebsite(input: string | null | undefined): string | null {
  if (!input) return null;
  const raw = input.trim();
  if (!raw) return null;
  if (!domainFromUrl(raw)) return null;
  return /^https?:\/\//i.test(raw) ? raw : `https://${raw}`;
}
