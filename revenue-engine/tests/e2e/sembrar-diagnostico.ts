/**
 * SOLO PARA PRUEBAS: crea una empresa de PRUEBA con un diagnóstico completo, pasando un sitio de ejemplo
 * local por el analizador real y una IA simulada (sin costo). Imprime la URL de la empresa.
 * Uso: NODE_ENV=test ANALYZER_ALLOW_PRIVATE=true DATABASE_URL=... npx tsx tests/e2e/sembrar-diagnostico.ts <BASE_URL>
 */
import http from "node:http";
import type { AddressInfo } from "node:net";
import { eq } from "drizzle-orm";
import { getDb } from "@/db";
import { companies, diagnoses, users } from "@/db/schema";
import type { ClaudeClient } from "@/server/analyzer/ai";
import { runDiagnosis } from "@/server/diagnosis";
import { BAD_SITE } from "../fixtures/sites";

if (process.env.NODE_ENV !== "test") {
  console.error("Este script es solo para pruebas (NODE_ENV=test).");
  process.exit(1);
}

const fakeClaude = {
  beta: {
    messages: {
      parse: async (params: { model: string }) => ({
        model: params.model,
        stop_reason: "end_turn",
        usage: { input_tokens: 2800, output_tokens: 900, cache_read_input_tokens: 0, cache_creation_input_tokens: 0 },
        parsed_output: {
          resumen:
            "(Texto de PRUEBA generado por una IA simulada.) El sitio tiene problemas básicos que afectan cómo se ve en celulares y cómo se miden las visitas, aunque la empresa ya invierte en publicidad.",
          problemas: [
            { titulo: "No se adapta a celulares", explicacion: "La mayoría de las visitas llegan desde el teléfono.", codigos: ["sin_version_celular"], prioridad: "alta" },
            { titulo: "Paga publicidad sin medir resultados", explicacion: "Tiene píxel de Meta pero no analítica.", codigos: ["sin_medicion", "invierte_en_publicidad"], prioridad: "alta" },
          ],
          servicios: [{ servicio: "Optimización de conversión", motivo: "Adaptar el sitio a celulares y agregar WhatsApp.", codigos: ["sin_version_celular", "sin_whatsapp"] }],
          estimaciones: [{ texto: "Podría estar perdiendo consultas de quienes entran desde el celular.", base: "No tiene viewport ni botón de WhatsApp." }],
          preguntas: ["¿Cuántas consultas reciben por mes y por qué canal?"],
          limitaciones: ["Solo se analizó la página principal."],
        },
      }),
    },
  },
} as unknown as ClaudeClient;

async function main() {
  const base = process.argv[2] ?? "http://localhost:3100";
  const server = http.createServer((_req, res) => {
    res.writeHead(200, { "content-type": "text/html" });
    res.end(BAD_SITE.replace("ventas@automotora-mala.example", "ventas@127.0.0.1.example"));
  });
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", () => r()));
  const site = `http://127.0.0.1:${(server.address() as AddressInfo).port}/`;
  const db = getDb();
  const [owner] = await db.select().from(users).where(eq(users.role, "owner")).limit(1);
  if (!owner) throw new Error("Primero hay que crear la cuenta del dueño.");
  const [company] = await db
    .insert(companies)
    .values({
      workspaceId: owner.workspaceId,
      name: "Automotora Mala (PRUEBA)",
      website: site,
      domain: "127.0.0.1",
      sector: "Automotoras",
      city: "Montevideo",
      source: "demo",
      isDemo: true,
    })
    .returning();
  const [d] = await db
    .insert(diagnoses)
    .values({ workspaceId: owner.workspaceId, companyId: company.id, status: "en_proceso", requestedBy: owner.id, isDemo: true })
    .returning();
  await runDiagnosis(d.id, { claude: fakeClaude });
  server.close();
  console.log(`${base}/empresas/${company.id}`);
  process.exit(0);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
