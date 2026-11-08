/**
 * Extrae hechos verificables del HTML de una página. Función pura: misma entrada, misma salida.
 */
import * as cheerio from "cheerio";
import type { SiteFacts } from "./types";

type Base = Pick<
  SiteFacts,
  "requestedUrl" | "finalUrl" | "fetchedAt" | "statusCode" | "responseMs" | "htmlBytes" | "redirects" | "robotsAllowed" | "httpRedirectsToHttps"
>;

const PLATFORM_PATTERNS: [string, RegExp][] = [
  ["Shopify", /cdn\.shopify\.com|Shopify\.theme|myshopify\.com/i],
  ["WooCommerce", /woocommerce/i],
  ["WordPress", /wp-content|wp-includes/i],
  ["Wix", /static\.wixstatic\.com|wix\.com/i],
  ["Tiendanube", /tiendanube|nuvemshop|d26lpennugtm8s\.cloudfront\.net/i],
  ["VTEX", /vteximg|vtexassets|vtex\.com/i],
  ["Mercado Shops", /mercadoshops/i],
  ["Squarespace", /squarespace/i],
  ["Magento", /mage\/|magento/i],
  ["PrestaShop", /prestashop/i],
  ["Jumpseller", /jumpseller/i],
  ["Webflow", /webflow/i],
];

const SOCIAL: [keyof SiteFacts["social"], RegExp][] = [
  ["facebook", /^https?:\/\/(www\.|m\.)?facebook\.com\/(?!sharer|share|plugins|dialog|tr\b)/i],
  ["instagram", /^https?:\/\/(www\.)?instagram\.com\/[^/?#]+/i],
  ["linkedin", /^https?:\/\/([a-z]+\.)?linkedin\.com\/(company|in|school)\//i],
  ["tiktok", /^https?:\/\/(www\.)?tiktok\.com\/@/i],
  ["youtube", /^https?:\/\/(www\.)?youtube\.com\/(channel|c|user|@)/i],
  ["x", /^https?:\/\/(www\.)?(twitter|x)\.com\/(?!intent|share)[^/?#]+/i],
];

const EMAIL_RE = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi;
const IGNORED_EMAIL = /\.(png|jpe?g|gif|webp|svg)$|@(sentry|example|domain|email|wixpress)\./i;

function uniq<T>(arr: T[]): T[] {
  return [...new Set(arr)];
}

function host(u: string): string {
  try {
    return new URL(u).hostname.toLowerCase().replace(/^www\./, "");
  } catch {
    return "";
  }
}

function normalizePhone(raw: string): string {
  return raw.replace(/[^\d+]/g, "");
}

export function extractFacts(html: string, base: Base, opts: { now?: Date } = {}): SiteFacts {
  const $ = cheerio.load(html);
  const pageUrl = base.finalUrl ?? base.requestedUrl;
  const siteHost = host(pageUrl);
  const isHttps = pageUrl.startsWith("https://");
  const abs = (href: string) => {
    try {
      return new URL(href, pageUrl).toString();
    } catch {
      return null;
    }
  };

  // Texto visible (sin scripts ni estilos)
  const $text = cheerio.load(html);
  $text("script, style, noscript, template, svg").remove();
  const visibleText = $text("body").text().replace(/\s+/g, " ").trim();
  const scriptsAndHtml = html;

  // Enlaces
  const links = $("a[href]")
    .map((_, el) => ($(el).attr("href") ?? "").trim())
    .get()
    .filter(Boolean);

  const whatsapp = uniq(
    links
      .filter((h) => /wa\.me\/|api\.whatsapp\.com\/send|web\.whatsapp\.com\/send|whatsapp:\/\//i.test(h))
      .map((h) => {
        const m = h.match(/wa\.me\/(\+?\d+)/i) ?? h.match(/phone=(\+?\d+)/i);
        return m ? normalizePhone(m[1]) : "enlace sin número";
      }),
  );
  const phones = uniq(links.filter((h) => /^tel:/i.test(h)).map((h) => normalizePhone(decodeURIComponent(h.slice(4)))).filter((p) => p.replace(/\D/g, "").length >= 6));

  const mailtos = links.filter((h) => /^mailto:/i.test(h)).map((h) => decodeURIComponent(h.slice(7).split("?")[0]).trim().toLowerCase());
  const textEmails = (visibleText.match(EMAIL_RE) ?? []).map((e) => e.toLowerCase());
  const emails = uniq([...mailtos, ...textEmails])
    .filter((e) => /^[^@\s]+@[^@\s]+\.[a-z]{2,}$/i.test(e) && !IGNORED_EMAIL.test(e))
    .slice(0, 20)
    .map((email) => {
      const d = email.split("@")[1];
      return { email, sameDomain: !!siteHost && (d === siteHost || d.endsWith(`.${siteHost}`) || siteHost.endsWith(`.${d}`)) };
    });

  const contactLink = links
    .map((h) => ({ h, url: abs(h) }))
    .find(({ h, url }) => url && host(url) === siteHost && /contact|contacto|contactanos|contáctenos/i.test(h));

  const social: SiteFacts["social"] = {};
  for (const h of links) {
    const url = abs(h);
    if (!url) continue;
    for (const [name, re] of SOCIAL) if (!social[name] && re.test(url)) social[name] = url;
  }

  // Medición y publicidad
  const ga4 = uniq(scriptsAndHtml.match(/\bG-[A-Z0-9]{6,12}\b/g) ?? []).filter(
    () => /gtag\(|googletagmanager\.com\/gtag/i.test(scriptsAndHtml),
  );
  const gtm = uniq(scriptsAndHtml.match(/\bGTM-[A-Z0-9]{4,10}\b/g) ?? []);
  const googleAds = uniq(scriptsAndHtml.match(/\bAW-\d{6,12}\b/g) ?? []);

  // Año del copyright más reciente en el texto visible
  const years = [...visibleText.matchAll(/(?:©|&copy;|copyright)\s*(?:\d{4}\s*[-–]\s*)?(\d{4})/gi)]
    .map((m) => Number(m[1]))
    .filter((y) => y >= 1995 && y <= (opts.now ?? new Date()).getFullYear() + 1);

  const jsonLdTypes: string[] = [];
  $('script[type="application/ld+json"]').each((_, el) => {
    try {
      const data = JSON.parse($(el).contents().text());
      const visit = (node: unknown) => {
        if (Array.isArray(node)) return node.forEach(visit);
        if (node && typeof node === "object") {
          const t = (node as Record<string, unknown>)["@type"];
          if (typeof t === "string") jsonLdTypes.push(t);
          if (Array.isArray(t)) t.forEach((x) => typeof x === "string" && jsonLdTypes.push(x));
          const graph = (node as Record<string, unknown>)["@graph"];
          if (graph) visit(graph);
        }
      };
      visit(data);
    } catch {
      /* JSON-LD inválido: se ignora */
    }
  });

  const images = $("img");
  const imagesWithoutAlt = images.filter((_, el) => !($(el).attr("alt") ?? "").trim()).length;

  const mixedContent = isHttps
    ? $("img[src^='http:'], script[src^='http:'], link[rel=stylesheet][href^='http:'], iframe[src^='http:']").length
    : 0;

  const lowerHtml = html.toLowerCase();
  const platform = PLATFORM_PATTERNS.filter(([, re]) => re.test(html)).map(([name]) => name);
  const ecommerceSignals =
    platform.some((p) => ["Shopify", "WooCommerce", "Tiendanube", "VTEX", "Mercado Shops", "Magento", "PrestaShop", "Jumpseller"].includes(p)) ||
    /agregar al carrito|añadir al carrito|add to cart|\/cart\b|\/carrito\b/i.test(html);

  const title = $("head title").first().text().replace(/\s+/g, " ").trim() || null;
  const metaDescription = ($('meta[name="description" i]').attr("content") ?? "").replace(/\s+/g, " ").trim() || null;

  return {
    ...base,
    error: null,
    https: isHttps,
    title,
    metaDescription,
    h1: $("h1")
      .map((_, el) => $(el).text().replace(/\s+/g, " ").trim())
      .get()
      .filter(Boolean)
      .slice(0, 5),
    lang: $("html").attr("lang")?.trim() || null,
    viewport: $('meta[name="viewport" i]').length > 0,
    canonical: $('link[rel="canonical"]').attr("href") ?? null,
    ogImage: $('meta[property="og:image"]').length > 0,
    jsonLdTypes: uniq(jsonLdTypes),
    wordCount: visibleText ? visibleText.split(" ").length : 0,
    imagesTotal: images.length,
    imagesWithoutAlt,
    mixedContent,
    copyrightYear: years.length ? Math.max(...years) : null,
    tracking: {
      ga4,
      gtm,
      universalAnalytics: /\bUA-\d{4,10}-\d+\b/.test(html) || /google-analytics\.com\/analytics\.js/i.test(html),
      googleAds,
      metaPixel: /connect\.facebook\.net\/[^"']*\/fbevents\.js|fbq\(\s*['"]init/i.test(html),
      tiktokPixel: /analytics\.tiktok\.com|ttq\.load/i.test(html),
      hotjarOrClarity: /static\.hotjar\.com|clarity\.ms/i.test(html),
    },
    contact: {
      whatsapp,
      phones,
      emails,
      forms: $("form").filter((_, el) => $(el).find("input, textarea").length >= 2).length,
      contactPageUrl: contactLink?.url ?? null,
    },
    social,
    platform,
    ecommerceSignals,
    privacyPolicy: /privacidad|privacy|protecci[oó]n de datos/i.test(lowerHtml),
    pagespeed: null,
  };
}

/** Hechos mínimos cuando el sitio no se pudo abrir. */
export function unreachableFacts(base: Base, error: string): SiteFacts {
  return {
    ...base,
    error,
    https: base.requestedUrl.startsWith("https://"),
    title: null,
    metaDescription: null,
    h1: [],
    lang: null,
    viewport: false,
    canonical: null,
    ogImage: false,
    jsonLdTypes: [],
    wordCount: 0,
    imagesTotal: 0,
    imagesWithoutAlt: 0,
    mixedContent: 0,
    copyrightYear: null,
    tracking: { ga4: [], gtm: [], universalAnalytics: false, googleAds: [], metaPixel: false, tiktokPixel: false, hotjarOrClarity: false },
    contact: { whatsapp: [], phones: [], emails: [], forms: 0, contactPageUrl: null },
    social: {},
    platform: [],
    ecommerceSignals: false,
    privacyPolicy: false,
    pagespeed: null,
  };
}
