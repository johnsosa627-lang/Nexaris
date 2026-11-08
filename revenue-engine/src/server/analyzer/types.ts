/**
 * Hechos medidos en el sitio web de una empresa. Todo lo que está acá se observó directamente
 * en la página (no hay estimaciones): por eso los hallazgos que salen de estos datos son "hechos".
 */
export type SiteFacts = {
  requestedUrl: string;
  finalUrl: string | null;
  fetchedAt: string;
  /** null si no se pudo abrir el sitio */
  statusCode: number | null;
  error: string | null;
  responseMs: number | null;
  htmlBytes: number | null;
  redirects: string[];
  robotsAllowed: boolean;
  https: boolean;
  /** ¿La versión http:// redirige a https://? null si no se comprobó */
  httpRedirectsToHttps: boolean | null;

  title: string | null;
  metaDescription: string | null;
  h1: string[];
  lang: string | null;
  viewport: boolean;
  canonical: string | null;
  ogImage: boolean;
  jsonLdTypes: string[];
  wordCount: number;
  imagesTotal: number;
  imagesWithoutAlt: number;
  /** Recursos http:// dentro de una página https:// */
  mixedContent: number;
  copyrightYear: number | null;

  tracking: {
    ga4: string[];
    gtm: string[];
    universalAnalytics: boolean;
    googleAds: string[];
    metaPixel: boolean;
    tiktokPixel: boolean;
    hotjarOrClarity: boolean;
  };
  contact: {
    whatsapp: string[];
    phones: string[];
    emails: { email: string; sameDomain: boolean }[];
    forms: number;
    contactPageUrl: string | null;
  };
  social: Partial<Record<"facebook" | "instagram" | "linkedin" | "tiktok" | "youtube" | "x", string>>;
  platform: string[];
  ecommerceSignals: boolean;
  privacyPolicy: boolean;

  pagespeed: PageSpeedResult | null;
};

export type PageSpeedResult =
  | {
      ok: true;
      strategy: "mobile";
      performance: number | null;
      seo: number | null;
      accessibility: number | null;
      bestPractices: number | null;
      lcpMs: number | null;
      cls: number | null;
    }
  | { ok: false; error: string };

export type Severity = "critica" | "alta" | "media" | "baja" | "info";
export type FindingCategory =
  | "seguridad"
  | "celular"
  | "seo"
  | "seo_local"
  | "medicion"
  | "publicidad"
  | "contacto"
  | "conversion"
  | "velocidad"
  | "confianza"
  | "acceso";

export type Finding = {
  /** Código estable de la regla (ej. "sin_https"): permite comparar diagnósticos en el tiempo. */
  code: string;
  kind: "hecho" | "estimacion" | "hipotesis";
  category: FindingCategory;
  severity: Severity;
  title: string;
  detail: string;
  evidence: string | null;
  sourceUrl: string | null;
  recommendation: string | null;
  service: string | null;
};

export type ScoreItem = { group: "necesidad" | "inversion" | "contacto"; label: string; points: number };
export type ScoreResult = { score: number; items: ScoreItem[]; groups: Record<ScoreItem["group"], { points: number; max: number }> };
