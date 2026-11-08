/**
 * Descarga segura de páginas públicas.
 *
 * - Solo http/https y puertos estándar.
 * - Bloquea direcciones internas (localhost, redes privadas, metadatos de la nube): así nadie puede
 *   usar el analizador para espiar la red del servidor escribiendo una URL rara. El control se hace
 *   en el momento de conectarse (no solo al principio), lo que también frena trucos de DNS.
 * - Límite de tiempo y de tamaño; máximo 5 redirecciones, cada una revisada.
 * - Respeta robots.txt.
 */
import { lookup as dnsLookup, type LookupAddress } from "node:dns";
import net from "node:net";
import { Agent, fetch as undiciFetch } from "undici";

export const USER_AGENT = "Mozilla/5.0 (compatible; RevenueEngineBot/1.0; analisis comercial)";
const MAX_BYTES = 3 * 1024 * 1024;
const TIMEOUT_MS = 15_000;
const MAX_REDIRECTS = 5;

const blocked = new net.BlockList();
for (const [net4, prefix] of [
  ["0.0.0.0", 8],
  ["10.0.0.0", 8],
  ["100.64.0.0", 10],
  ["127.0.0.0", 8],
  ["169.254.0.0", 16],
  ["172.16.0.0", 12],
  ["192.0.0.0", 24],
  ["192.0.2.0", 24],
  ["192.168.0.0", 16],
  ["198.18.0.0", 15],
  ["198.51.100.0", 24],
  ["203.0.113.0", 24],
  ["224.0.0.0", 4],
  ["240.0.0.0", 4],
] as const) {
  blocked.addSubnet(net4, prefix, "ipv4");
}
for (const [net6, prefix] of [
  ["::", 128],
  ["::1", 128],
  ["fc00::", 7],
  ["fe80::", 10],
  ["ff00::", 8],
  ["64:ff9b::", 96],
  ["2001:db8::", 32],
] as const) {
  blocked.addSubnet(net6, prefix, "ipv6");
}

/** ¿Es una dirección pública de internet? */
export function isPublicAddress(address: string): boolean {
  const family = net.isIP(address);
  if (family === 0) return false;
  if (family === 6) {
    const mapped = address.toLowerCase().match(/^::ffff:(\d+\.\d+\.\d+\.\d+)$/);
    if (mapped) return isPublicAddress(mapped[1]);
    return !blocked.check(address, "ipv6");
  }
  return !blocked.check(address, "ipv4");
}

/** Solo en pruebas automáticas se permite analizar sitios locales de ejemplo. */
function allowPrivate(): boolean {
  return process.env.NODE_ENV === "test" && process.env.ANALYZER_ALLOW_PRIVATE === "true";
}

const agent = new Agent({
  connect: {
    timeout: TIMEOUT_MS,
    lookup(hostname, options, callback) {
      dnsLookup(hostname, { ...options, all: true }, (err, addresses) => {
        if (err) return callback(err, "", 4);
        const list = (Array.isArray(addresses) ? addresses : [addresses]) as LookupAddress[];
        const bad = list.find((a) => !isPublicAddress(a.address));
        if (bad && !allowPrivate()) {
          return callback(new Error(`Dirección no permitida (${hostname} apunta a una red interna).`), "", 4);
        }
        if (options.all) return callback(null, list as unknown as string, 4);
        return callback(null, list[0].address, list[0].family);
      });
    },
  },
});

export class FetchError extends Error {}

export type FetchResult = {
  finalUrl: string;
  status: number;
  contentType: string;
  body: string;
  ms: number;
  redirects: string[];
};

function checkUrl(raw: string): URL {
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    throw new FetchError("La dirección no es válida.");
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") throw new FetchError("Solo se analizan direcciones http o https.");
  if (url.port && url.port !== "80" && url.port !== "443" && !allowPrivate()) {
    throw new FetchError("Solo se analizan sitios en los puertos estándar.");
  }
  if (url.username || url.password) throw new FetchError("La dirección no puede incluir usuario o contraseña.");
  // Una IP escrita directamente no pasa por el DNS: hay que revisarla acá.
  const hostIp = url.hostname.replace(/^\[|\]$/g, "");
  if (net.isIP(hostIp) && !isPublicAddress(hostIp) && !allowPrivate()) {
    throw new FetchError("Dirección no permitida (apunta a una red interna).");
  }
  return url;
}

async function readLimited(res: Awaited<ReturnType<typeof undiciFetch>>): Promise<string> {
  if (!res.body) return "";
  const reader = res.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > MAX_BYTES) {
      await reader.cancel();
      break;
    }
    chunks.push(value);
  }
  return Buffer.concat(chunks).toString("utf8");
}

/** Descarga una página siguiendo redirecciones de forma segura. */
export async function safeFetch(rawUrl: string, opts: { accept?: string } = {}): Promise<FetchResult> {
  const started = Date.now();
  const redirects: string[] = [];
  let url = checkUrl(rawUrl);
  for (let i = 0; i <= MAX_REDIRECTS; i++) {
    let res;
    try {
      res = await undiciFetch(url, {
        dispatcher: agent,
        redirect: "manual",
        signal: AbortSignal.timeout(TIMEOUT_MS),
        headers: {
          "user-agent": USER_AGENT,
          accept: opts.accept ?? "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
          "accept-language": "es-UY,es;q=0.9",
        },
      });
    } catch (err) {
      const cause = (err as { cause?: { message?: string; code?: string } }).cause;
      const msg = cause?.message ?? (err as Error).message;
      if (/timeout|aborted/i.test(msg)) throw new FetchError("El sitio tardó demasiado en responder.");
      if (/ENOTFOUND|EAI_AGAIN/i.test(msg) || cause?.code === "ENOTFOUND") throw new FetchError("El dominio no existe o no responde (DNS).");
      if (/certificate|SSL|TLS/i.test(msg)) throw new FetchError("El certificado de seguridad (https) del sitio tiene un problema.");
      throw new FetchError(msg.startsWith("Dirección no permitida") ? msg : `No se pudo conectar: ${msg}`);
    }
    if (res.status >= 300 && res.status < 400 && res.headers.get("location")) {
      await res.body?.cancel();
      const next = new URL(res.headers.get("location")!, url);
      redirects.push(next.toString());
      url = checkUrl(next.toString());
      continue;
    }
    const contentType = res.headers.get("content-type") ?? "";
    const body = await readLimited(res);
    return { finalUrl: url.toString(), status: res.status, contentType, body, ms: Date.now() - started, redirects };
  }
  throw new FetchError("Demasiadas redirecciones.");
}

// ---------- robots.txt ----------

/** Interpreta robots.txt y dice si nuestro robot puede leer esa ruta. */
export function robotsAllows(robotsTxt: string, path: string, agentName = "revenueenginebot"): boolean {
  type Group = { agents: string[]; rules: { allow: boolean; path: string }[] };
  const groups: Group[] = [];
  let current: Group | null = null;
  let lastWasAgent = false;
  for (const rawLine of robotsTxt.split(/\r?\n/)) {
    const line = rawLine.replace(/#.*/, "").trim();
    if (!line) continue;
    const idx = line.indexOf(":");
    if (idx < 0) continue;
    const key = line.slice(0, idx).trim().toLowerCase();
    const value = line.slice(idx + 1).trim();
    if (key === "user-agent") {
      if (!current || !lastWasAgent) {
        current = { agents: [], rules: [] };
        groups.push(current);
      }
      current.agents.push(value.toLowerCase());
      lastWasAgent = true;
    } else if ((key === "allow" || key === "disallow") && current) {
      lastWasAgent = false;
      if (value || key === "allow") current.rules.push({ allow: key === "allow", path: value });
    } else {
      lastWasAgent = false;
    }
  }
  const specific = groups.filter((g) => g.agents.some((a) => a !== "*" && agentName.includes(a)));
  const chosen = specific.length ? specific : groups.filter((g) => g.agents.includes("*"));
  let best: { allow: boolean; len: number } | null = null;
  for (const g of chosen) {
    for (const r of g.rules) {
      if (!r.path) continue;
      const pattern = new RegExp(
        "^" + r.path.replace(/[.+?^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*").replace(/\\\$$/, "$"),
      );
      if (pattern.test(path) && (!best || r.path.length > best.len || (r.path.length === best.len && r.allow))) {
        best = { allow: r.allow, len: r.path.length };
      }
    }
  }
  return best ? best.allow : true;
}

export async function checkRobots(pageUrl: string): Promise<boolean> {
  const url = new URL(pageUrl);
  try {
    const res = await safeFetch(`${url.origin}/robots.txt`, { accept: "text/plain,*/*" });
    if (res.status >= 400) return true; // sin robots.txt = permitido
    if (!/text\/plain/i.test(res.contentType) && /<html/i.test(res.body)) return true;
    return robotsAllows(res.body, url.pathname + url.search);
  } catch {
    return true; // si robots.txt no responde, se asume permitido (criterio estándar)
  }
}
