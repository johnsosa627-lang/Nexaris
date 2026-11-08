/**
 * Google PageSpeed Insights (API oficial y gratuita). Necesita PAGESPEED_API_KEY: sin clave, Google
 * limita mucho las consultas. Si no hay clave o falla, el diagnóstico sigue sin este dato y lo dice.
 */
import type { PageSpeedResult } from "./types";

export async function runPageSpeed(url: string): Promise<PageSpeedResult | null> {
  const key = process.env.PAGESPEED_API_KEY;
  if (!key) return null;
  const api = new URL("https://www.googleapis.com/pagespeedonline/v5/runPagespeed");
  api.searchParams.set("url", url);
  api.searchParams.set("strategy", "mobile");
  for (const c of ["performance", "seo", "accessibility", "best-practices"]) api.searchParams.append("category", c);
  api.searchParams.set("key", key);
  try {
    const res = await fetch(api, { signal: AbortSignal.timeout(90_000) });
    if (!res.ok) return { ok: false, error: `PageSpeed respondió ${res.status}` };
    const data = (await res.json()) as {
      lighthouseResult?: {
        categories?: Record<string, { score: number | null }>;
        audits?: Record<string, { numericValue?: number }>;
      };
    };
    const cats = data.lighthouseResult?.categories ?? {};
    const audits = data.lighthouseResult?.audits ?? {};
    const pct = (k: string) => (cats[k]?.score == null ? null : Math.round((cats[k].score as number) * 100));
    return {
      ok: true,
      strategy: "mobile",
      performance: pct("performance"),
      seo: pct("seo"),
      accessibility: pct("accessibility"),
      bestPractices: pct("best-practices"),
      lcpMs: audits["largest-contentful-paint"]?.numericValue ?? null,
      cls: audits["cumulative-layout-shift"]?.numericValue ?? null,
    };
  } catch (err) {
    return { ok: false, error: `PageSpeed no respondió: ${(err as Error).message}` };
  }
}
