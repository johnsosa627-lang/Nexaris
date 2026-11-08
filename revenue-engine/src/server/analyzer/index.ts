/**
 * Análisis completo de un sitio: robots.txt → página principal → http→https → PageSpeed (opcional)
 * → hallazgos → puntuación. Sin IA: todo es medible y repetible.
 */
import { extractFacts, unreachableFacts } from "./extract";
import { checkRobots, FetchError, safeFetch } from "./fetcher";
import { runPageSpeed } from "./pagespeed";
import { buildFindings } from "./rules";
import { computeScore } from "./score";
import type { Finding, ScoreResult, SiteFacts } from "./types";

export type SiteAnalysis = { facts: SiteFacts; findings: Finding[]; score: ScoreResult };

export async function analyzeSite(url: string, opts: { now?: Date } = {}): Promise<SiteAnalysis> {
  const now = opts.now ?? new Date();
  const base = {
    requestedUrl: url,
    finalUrl: null as string | null,
    fetchedAt: now.toISOString(),
    statusCode: null as number | null,
    responseMs: null as number | null,
    htmlBytes: null as number | null,
    redirects: [] as string[],
    robotsAllowed: true,
    httpRedirectsToHttps: null as boolean | null,
  };

  let facts: SiteFacts;
  base.robotsAllowed = await checkRobots(url);
  if (!base.robotsAllowed) {
    facts = unreachableFacts(base, "robots.txt no permite el análisis");
    facts.error = null; // no es un error del sitio: es una decisión de la empresa que respetamos
  } else {
    try {
      const page = await safeFetch(url);
      base.finalUrl = page.finalUrl;
      base.statusCode = page.status;
      base.responseMs = page.ms;
      base.htmlBytes = Buffer.byteLength(page.body);
      base.redirects = page.redirects;
      if (!/html/i.test(page.contentType) && !/<html/i.test(page.body.slice(0, 2000))) {
        facts = unreachableFacts(base, `La dirección no devuelve una página web (tipo: ${page.contentType || "desconocido"}).`);
      } else {
        if (page.finalUrl.startsWith("https://")) {
          try {
            const http = await safeFetch(`http://${new URL(page.finalUrl).host}/`);
            base.httpRedirectsToHttps = http.finalUrl.startsWith("https://");
          } catch {
            base.httpRedirectsToHttps = null; // no se pudo comprobar: no se afirma nada
          }
        }
        facts = extractFacts(page.body, base, { now });
        facts.pagespeed = await runPageSpeed(page.finalUrl);
      }
    } catch (err) {
      const message = err instanceof FetchError ? err.message : `Error inesperado: ${(err as Error).message}`;
      facts = unreachableFacts(base, message);
    }
  }

  const findings = buildFindings(facts, { now });
  const score = computeScore(facts, findings);
  return { facts, findings, score };
}

export type { Finding, ScoreResult, SiteFacts } from "./types";
