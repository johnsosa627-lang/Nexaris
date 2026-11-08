import http from "node:http";
import type { AddressInfo } from "node:net";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { BAD_SITE, GOOD_SITE } from "./fixtures/sites";
import { analyzeSite } from "@/server/analyzer";
import { costMillicents, validateSummary, type AiSummary } from "@/server/analyzer/ai";
import { extractFacts } from "@/server/analyzer/extract";
import { isPublicAddress, robotsAllows, safeFetch } from "@/server/analyzer/fetcher";
import { buildFindings } from "@/server/analyzer/rules";
import { computeScore } from "@/server/analyzer/score";

const NOW = new Date("2026-11-08T12:00:00Z");
const base = (url: string) => ({
  requestedUrl: url,
  finalUrl: url,
  fetchedAt: NOW.toISOString(),
  statusCode: 200,
  responseMs: 120,
  htmlBytes: 1000,
  redirects: [],
  robotsAllowed: true,
  httpRedirectsToHttps: true,
});

describe("protección de red (el analizador no puede espiar la red interna)", () => {
  it("reconoce direcciones internas y públicas", () => {
    for (const ip of ["127.0.0.1", "10.1.2.3", "172.20.0.5", "192.168.1.1", "169.254.169.254", "0.0.0.0", "::1", "fe80::1", "fd00::1", "::ffff:10.0.0.1", "100.64.1.1"]) {
      expect(isPublicAddress(ip), ip).toBe(false);
    }
    for (const ip of ["8.8.8.8", "190.64.1.1", "2800:a4:1::1"]) expect(isPublicAddress(ip), ip).toBe(true);
    expect(isPublicAddress("no-es-ip")).toBe(false);
  });

  it("bloquea localhost aunque se pida directamente", async () => {
    const prev = process.env.ANALYZER_ALLOW_PRIVATE;
    delete process.env.ANALYZER_ALLOW_PRIVATE;
    try {
      await expect(safeFetch("http://localhost/")).rejects.toThrow(/red interna|puertos/);
      await expect(safeFetch("http://127.0.0.1/")).rejects.toThrow(/red interna/);
      await expect(safeFetch("http://2130706433/")).rejects.toThrow(/red interna/); // 127.0.0.1 disfrazado
      await expect(safeFetch("http://[::1]/")).rejects.toThrow(/red interna/);
      await expect(safeFetch("http://169.254.169.254/latest/meta-data")).rejects.toThrow(/red interna/);
    } finally {
      if (prev) process.env.ANALYZER_ALLOW_PRIVATE = prev;
    }
  });

  it("rechaza esquemas y direcciones raras", async () => {
    await expect(safeFetch("ftp://ejemplo.com/")).rejects.toThrow(/http o https/);
    await expect(safeFetch("https://user:pass@ejemplo.com/")).rejects.toThrow(/usuario/);
    await expect(safeFetch("no es url")).rejects.toThrow(/no es válida/);
  });
});

describe("robots.txt", () => {
  it("respeta Disallow y Allow", () => {
    const txt = "User-agent: *\nDisallow: /privado\nAllow: /privado/publico\n\nUser-agent: OtroBot\nDisallow: /";
    expect(robotsAllows(txt, "/")).toBe(true);
    expect(robotsAllows(txt, "/privado/x")).toBe(false);
    expect(robotsAllows(txt, "/privado/publico/y")).toBe(true);
    expect(robotsAllows("User-agent: *\nDisallow: /", "/")).toBe(false);
    expect(robotsAllows("User-agent: RevenueEngineBot\nDisallow: /\n\nUser-agent: *\nAllow: /", "/")).toBe(false);
    expect(robotsAllows("User-agent: *\nDisallow:", "/")).toBe(true);
    expect(robotsAllows("", "/")).toBe(true);
  });
});

describe("extracción de hechos", () => {
  it("sitio con problemas", () => {
    const f = extractFacts(BAD_SITE, base("https://automotora-mala.example/"), { now: NOW });
    expect(f.viewport).toBe(false);
    expect(f.metaDescription).toBeNull();
    expect(f.h1).toHaveLength(2);
    expect(f.tracking.metaPixel).toBe(true);
    expect(f.tracking.ga4).toHaveLength(0);
    expect(f.contact.emails).toEqual([{ email: "ventas@automotora-mala.example", sameDomain: true }]);
    expect(f.contact.whatsapp).toHaveLength(0);
    expect(f.copyrightYear).toBe(2019);
    expect(f.imagesWithoutAlt).toBe(4);
    expect(f.mixedContent).toBe(1);
  });

  it("sitio bien hecho", () => {
    const f = extractFacts(GOOD_SITE, base("https://inmo-buena.example/"), { now: NOW });
    expect(f.viewport).toBe(true);
    expect(f.lang).toBe("es");
    expect(f.tracking.ga4).toEqual(["G-ABC1234567"]);
    expect(f.tracking.googleAds).toEqual(["AW-123456789"]);
    expect(f.contact.whatsapp).toEqual(["59899123456"]);
    expect(f.contact.phones).toEqual(["+59821234567"]);
    expect(f.contact.forms).toBe(1);
    expect(f.contact.contactPageUrl).toBe("https://inmo-buena.example/contacto");
    expect(Object.keys(f.social).sort()).toEqual(["facebook", "instagram"]);
    expect(f.jsonLdTypes).toEqual(["RealEstateAgent"]);
    expect(f.privacyPolicy).toBe(true);
  });
});

describe("hallazgos y puntuación", () => {
  it("un sitio con problemas genera hallazgos con evidencia y puntúa alto en necesidad", () => {
    const f = extractFacts(BAD_SITE, base("https://automotora-mala.example/"), { now: NOW });
    const findings = buildFindings(f, { now: NOW });
    const codes = findings.map((x) => x.code);
    expect(codes).toEqual(
      expect.arrayContaining(["sin_version_celular", "sin_descripcion", "varios_h1", "sin_medicion", "sin_whatsapp", "sitio_desactualizado", "contenido_mixto", "imagenes_sin_alt", "titulo_largo_o_corto", "invierte_en_publicidad"]),
    );
    expect(findings.every((x) => x.kind === "hecho" && x.evidence && x.sourceUrl)).toBe(true);
    // Tiene publicidad pero no analítica → la falta de medición es grave
    expect(findings.find((x) => x.code === "sin_medicion")?.severity).toBe("alta");
    const score = computeScore(f, findings);
    expect(score.groups.necesidad.points).toBe(50);
    expect(score.groups.necesidad.max).toBe(50);
    expect(score.score).toBeLessThanOrEqual(100);
  });

  it("un sitio bien hecho tiene pocos hallazgos y la necesidad es baja", () => {
    const f = extractFacts(GOOD_SITE, base("https://inmo-buena.example/"), { now: NOW });
    const findings = buildFindings(f, { now: NOW });
    const problems = findings.filter((x) => x.severity !== "info");
    expect(problems).toHaveLength(0);
    const score = computeScore(f, findings);
    expect(score.groups.necesidad.points).toBe(0);
    expect(score.groups.contacto.points).toBe(25);
  });

  it("si el sitio no responde, no se inventan otros problemas", () => {
    const findings = buildFindings(
      { ...extractFacts("<html></html>", base("https://x.example/"), { now: NOW }), error: "El sitio tardó demasiado en responder." },
      { now: NOW },
    );
    expect(findings.map((f) => f.code)).toEqual(["sitio_no_responde"]);
  });
});

describe("análisis completo contra un servidor de ejemplo", () => {
  let server: http.Server;
  let origin = "";
  beforeAll(async () => {
    process.env.ANALYZER_ALLOW_PRIVATE = "true";
    server = http.createServer((req, res) => {
      if (req.url === "/robots.txt") {
        res.writeHead(200, { "content-type": "text/plain" });
        return res.end("User-agent: *\nDisallow: /privado");
      }
      if (req.url === "/redirige") {
        res.writeHead(301, { location: "/malo" });
        return res.end();
      }
      if (req.url === "/malo") {
        res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
        return res.end(BAD_SITE);
      }
      if (req.url === "/imagen") {
        res.writeHead(200, { "content-type": "image/png" });
        return res.end("PNG");
      }
      res.writeHead(200, { "content-type": "text/html" });
      res.end(GOOD_SITE);
    });
    await new Promise<void>((r) => server.listen(0, "127.0.0.1", () => r()));
    origin = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  });
  afterAll(() => {
    server.close();
    delete process.env.ANALYZER_ALLOW_PRIVATE;
  });

  it("sigue redirecciones y analiza", async () => {
    const a = await analyzeSite(`${origin}/redirige`, { now: NOW });
    expect(a.facts.finalUrl).toBe(`${origin}/malo`);
    expect(a.facts.redirects).toHaveLength(1);
    expect(a.facts.https).toBe(false);
    expect(a.findings.some((f) => f.code === "sin_https")).toBe(true);
    expect(a.score.score).toBeGreaterThan(50);
  });

  it("respeta robots.txt: no analiza páginas prohibidas", async () => {
    const a = await analyzeSite(`${origin}/privado/pagina`, { now: NOW });
    expect(a.facts.robotsAllowed).toBe(false);
    expect(a.findings.map((f) => f.code)).toEqual(["robots_bloquea"]);
    expect(a.score.score).toBe(0);
  });

  it("detecta cuando la dirección no es una página web", async () => {
    const a = await analyzeSite(`${origin}/imagen`, { now: NOW });
    expect(a.facts.error).toMatch(/no devuelve una página web/);
  });

  it("informa si el sitio no responde", async () => {
    const a = await analyzeSite("http://127.0.0.1:1/", { now: NOW });
    expect(a.facts.error).toBeTruthy();
    expect(a.findings[0].code).toBe("sitio_no_responde");
  });
});

describe("IA: costos y validación", () => {
  it("calcula costos con los precios de cada modelo", () => {
    // 1 millón de tokens de entrada en Opus 5.5 = US$4 = 400.000 milicentavos
    expect(costMillicents("claude-opus-5-5", 1_000_000, 0)).toBe(400_000);
    expect(costMillicents("claude-haiku-5-5", 0, 1_000_000)).toBe(50_000);
  });

  it("descarta lo que la IA no respalde con hallazgos reales", () => {
    const s: AiSummary = {
      resumen: "x",
      problemas: [
        { titulo: "Real", explicacion: "e", codigos: ["sin_whatsapp"], prioridad: "alta" },
        { titulo: "Inventado", explicacion: "e", codigos: ["no_existe"], prioridad: "alta" },
      ],
      servicios: [{ servicio: "SEO", motivo: "m", codigos: ["inventado"] }],
      estimaciones: [],
      preguntas: [],
      limitaciones: [],
    };
    const findings = buildFindings(extractFacts(BAD_SITE, base("https://a.example/"), { now: NOW }), { now: NOW });
    const { summary, discarded } = validateSummary(s, findings);
    expect(summary.problemas.map((p) => p.titulo)).toEqual(["Real"]);
    expect(summary.servicios).toHaveLength(0);
    expect(discarded).toBe(2);
  });
});
