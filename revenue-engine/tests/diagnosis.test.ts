import http from "node:http";
import type { AddressInfo } from "node:net";
import { eq } from "drizzle-orm";
import { afterAll, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { BAD_SITE } from "./fixtures/sites";
import { makeWorkspace } from "./helpers";
import { getDb } from "@/db";
import { aiUsage, companies, findings } from "@/db/schema";
import type { ClaudeClient } from "@/server/analyzer/ai";
import { updateAgentSettings } from "@/server/agents";
import type { Ctx } from "@/server/context";
import { createCompany, getCompanyDetail } from "@/server/crm";
import { getDiagnoses, processQueue, requestDiagnosis, requestPendingDiagnoses } from "@/server/diagnosis";
import { decideApproval } from "@/server/gateway";
import { importCompanies, parseCompanyList } from "@/server/importer";
import { pauseAutomations, resumeAutomations, setPolicyLevel, updateLimits } from "@/server/security";

let server: http.Server;
let origin = "";
let calls = 0;

/** Cliente de Claude de prueba: responde como la API real, sin gastar. */
function fakeClaude(codes = ["sin_whatsapp", "inventado"]): ClaudeClient {
  return {
    beta: {
      messages: {
        parse: async (params: { model: string }) => {
          calls++;
          return {
            model: params.model,
            stop_reason: "end_turn",
            usage: { input_tokens: 3000, output_tokens: 1200, cache_read_input_tokens: 0, cache_creation_input_tokens: 0 },
            parsed_output: {
              resumen: "Sitio con varios problemas solucionables.",
              problemas: codes.map((c) => ({ titulo: `Problema ${c}`, explicacion: "x", codigos: [c], prioridad: "alta" })),
              servicios: [{ servicio: "Conversión", motivo: "m", codigos: ["sin_whatsapp"] }],
              estimaciones: [{ texto: "Podría estar perdiendo consultas", base: "sin WhatsApp" }],
              preguntas: ["¿Cuántas consultas reciben por mes?"],
              limitaciones: ["Solo se analizó la página principal"],
            },
          };
        },
      },
    },
  } as unknown as ClaudeClient;
}

beforeAll(async () => {
  process.env.ANALYZER_ALLOW_PRIVATE = "true";
  server = http.createServer((_req, res) => {
    res.writeHead(200, { "content-type": "text/html" });
    res.end(BAD_SITE);
  });
  await new Promise<void>((r) => server.listen(0, "0.0.0.0", () => r()));
  origin = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => {
  server.close();
  delete process.env.ANALYZER_ALLOW_PRIVATE;
});

let ctx: Ctx;
beforeEach(async () => {
  calls = 0;
  ctx = await makeWorkspace();
});

async function enableDirector(budgetCents = 0) {
  await updateAgentSettings(ctx, "director", { enabled: true, model: "claude-opus-5-5", monthlyBudgetCents: budgetCents, instructions: "" });
}

async function companyWithSite(name = "Automotora Mala") {
  return createCompany(ctx, { name, website: `${origin}/` });
}

describe("pedir diagnósticos", () => {
  it("exige sitio web y el Director encendido", async () => {
    const sinWeb = await createCompany(ctx, { name: "Sin web" });
    await expect(requestDiagnosis(ctx, sinWeb.id)).rejects.toThrow(/sitio web/);
    const c = await companyWithSite();
    await expect(requestDiagnosis(ctx, c.id)).rejects.toThrow(/Director General está apagado/);
  });

  it("no encola dos veces la misma empresa", async () => {
    await enableDirector();
    const c = await companyWithSite();
    const a = await requestDiagnosis(ctx, c.id);
    const b = await requestDiagnosis(ctx, c.id);
    expect(a.status).toBe("en_cola");
    expect(b).toMatchObject({ status: "en_cola", alreadyQueued: true });
  });

  it("con las automatizaciones detenidas no se puede pedir ni se procesa la cola", async () => {
    await enableDirector();
    const c = await companyWithSite();
    await requestDiagnosis(ctx, c.id);
    await pauseAutomations(ctx, "prueba");
    await expect(requestDiagnosis(ctx, c.id)).rejects.toThrow(/detenidas/);
    expect(await processQueue({ claude: fakeClaude() })).toBe(0);
    await resumeAutomations(ctx);
    expect(await processQueue({ claude: fakeClaude() })).toBe(1);
  });

  it("si el diagnóstico se sube a Nivel 2, queda esperando aprobación y al aprobarse se encola", async () => {
    await enableDirector();
    await setPolicyLevel(ctx, "preparar_diagnostico", 2);
    const c = await companyWithSite();
    const r = await requestDiagnosis(ctx, c.id);
    expect(r.status).toBe("requiere_aprobacion");
    if (r.status !== "requiere_aprobacion") return;
    const decided = await decideApproval(ctx, { approvalId: r.approvalId, decision: "aprobar" });
    expect(decided?.status).toBe("ejecutada");
    expect((await getDiagnoses(ctx, c.id)).pending).not.toBeNull();
  });
});

describe("ejecutar diagnósticos", () => {
  it("analiza, guarda hallazgos, puntúa, pasa a 'investigado' y registra el costo real de la IA", async () => {
    await enableDirector();
    const c = await companyWithSite();
    await requestDiagnosis(ctx, c.id);
    expect(await processQueue({ claude: fakeClaude() })).toBe(1);

    const { latestDone, latestFindings } = await getDiagnoses(ctx, c.id);
    expect(latestDone?.status).toBe("listo");
    expect(latestDone?.score).toBeGreaterThan(50);
    expect(latestFindings.length).toBeGreaterThan(3);
    expect(latestFindings.every((f) => f.kind === "hecho")).toBe(true);

    // La IA citó un código inventado: se descartó
    const summary = latestDone?.aiSummary as { problemas: { titulo: string }[] };
    expect(summary.problemas.map((p) => p.titulo)).toEqual(["Problema sin_whatsapp"]);
    expect(latestDone?.aiNote).toMatch(/Se descartaron 1/);

    const usage = await getDb().select().from(aiUsage);
    expect(usage).toHaveLength(1);
    // 3000 * 4 * 0.1 + 1200 * 20 * 0.1 = 1200 + 2400 = 3600 milicentavos = US$0,036
    expect(usage[0].costMillicents).toBe(3600);
    expect(latestDone?.costCents).toBe(4);

    const [co] = await getDb().select().from(companies).where(eq(companies.id, c.id));
    expect(co.stage).toBe("investigado");
    expect(co.opportunityScore).toBe(latestDone?.score);
    const detail = await getCompanyDetail(ctx, c.id);
    expect(detail.activities[0].title).toMatch(/Diagnóstico listo/);
  });

  it("sin clave de Anthropic guarda el diagnóstico igual, sin resumen y explicando por qué", async () => {
    const prev = process.env.ANTHROPIC_API_KEY;
    delete process.env.ANTHROPIC_API_KEY;
    try {
      await enableDirector();
      const c = await companyWithSite();
      await requestDiagnosis(ctx, c.id);
      await processQueue();
      const { latestDone } = await getDiagnoses(ctx, c.id);
      expect(latestDone?.status).toBe("listo");
      expect(latestDone?.aiSummary).toBeNull();
      expect(latestDone?.aiNote).toMatch(/No hay clave de Anthropic/);
    } finally {
      if (prev) process.env.ANTHROPIC_API_KEY = prev;
    }
  });

  it("respeta el tope mensual de IA: no llama a la IA si se pasaría", async () => {
    await enableDirector();
    await updateLimits(ctx, { aiMonthlyBudgetCents: 1, maxSpendPerActionCents: 0, dailyEmailLimit: 20 });
    const c = await companyWithSite();
    await requestDiagnosis(ctx, c.id);
    await processQueue({ claude: fakeClaude() });
    const { latestDone } = await getDiagnoses(ctx, c.id);
    expect(calls).toBe(0);
    expect(latestDone?.aiNote).toMatch(/tope mensual/);
  });

  it("respeta el presupuesto propio del Director", async () => {
    await enableDirector(1); // 1 centavo
    const c = await companyWithSite();
    await requestDiagnosis(ctx, c.id);
    await processQueue({ claude: fakeClaude() });
    expect(calls).toBe(0);
    expect((await getDiagnoses(ctx, c.id)).latestDone?.aiNote).toMatch(/presupuesto mensual del Director/);
  });

  it("un sitio que no responde queda como diagnóstico con ese hallazgo y sin gastar IA", async () => {
    await enableDirector();
    const c = await createCompany(ctx, { name: "Caída", website: "http://127.0.0.1:1/" });
    await requestDiagnosis(ctx, c.id);
    await processQueue({ claude: fakeClaude() });
    const { latestDone, latestFindings } = await getDiagnoses(ctx, c.id);
    expect(latestDone?.status).toBe("listo");
    expect(latestFindings.map((f) => f.code)).toEqual(["sitio_no_responde"]);
    expect(calls).toBe(0);
  });

  it("analiza en lote las empresas con web que aún no tienen diagnóstico", async () => {
    await enableDirector();
    await companyWithSite("Empresa A");
    await createCompany(ctx, { name: "Empresa B", website: `${origin.replace("127.0.0.1", "127.0.0.2")}/b` });
    await createCompany(ctx, { name: "Sin web" });
    const r = await requestPendingDiagnoses(ctx);
    expect(r).toMatchObject({ queued: 2, found: 2 });
    expect(await processQueue({ claude: fakeClaude() })).toBe(2);
    expect((await requestPendingDiagnoses(ctx)).found).toBe(0);
    expect((await getDb().select().from(findings)).length).toBeGreaterThan(0);
  });

  it("otro espacio de trabajo no ve los diagnósticos", async () => {
    await enableDirector();
    const c = await companyWithSite();
    await requestDiagnosis(ctx, c.id);
    const otro = await makeWorkspace("Otro");
    expect((await getDiagnoses(otro, c.id)).list).toHaveLength(0);
    await expect(requestDiagnosis(otro, c.id)).rejects.toThrow(/no encontrada/);
  });
});

describe("importar empresas", () => {
  it("entiende listas pegadas de planillas (tabulador con títulos, punto y coma, comas con comillas)", () => {
    expect(parseCompanyList("Empresa\tWeb\tCiudad\nAutos Uno\tautosuno.com.uy\tSalto")).toEqual([
      { name: "Autos Uno", website: "autosuno.com.uy", city: "Salto", sector: "" },
    ]);
    expect(parseCompanyList("Inmo Dos;inmodos.uy;Montevideo;Inmobiliarias")).toEqual([
      { name: "Inmo Dos", website: "inmodos.uy", city: "Montevideo", sector: "Inmobiliarias" },
    ]);
    expect(parseCompanyList('"Tienda, Tres",tienda3.uy')[0].name).toBe("Tienda, Tres");
    expect(parseCompanyList("sitio web\ntienda4.uy")).toEqual([{ name: "", website: "tienda4.uy", city: "", sector: "" }]);
  });

  it("crea las nuevas y explica las que saltea", async () => {
    await createCompany(ctx, { name: "Ya está", website: "yaesta.uy" });
    const r = await importCompanies(ctx, "Nueva Uno\tnueva1.uy\nRepetida\twww.yaesta.uy\nEmpresa X\tno es web\n\tsolo-web.uy", {
      sector: "Inmobiliarias",
      city: "Montevideo",
    });
    expect(r.created).toBe(2);
    expect(r.skipped.map((s) => s.reason)).toEqual([expect.stringMatching(/Ya existe/), expect.stringMatching(/no es válida/)]);
    const detail = await getDb().select().from(companies).where(eq(companies.domain, "solo-web.uy"));
    expect(detail[0]).toMatchObject({ name: "solo-web.uy", sector: "Inmobiliarias", source: "planilla" });
  });

  it("rechaza listas vacías o demasiado grandes", async () => {
    await expect(importCompanies(ctx, "  \n ")).rejects.toThrow(/No se encontraron/);
    const big = Array.from({ length: 201 }, (_, i) => `E${i}\te${i}.uy`).join("\n");
    await expect(importCompanies(ctx, big)).rejects.toThrow(/hasta 200/);
  });
});
