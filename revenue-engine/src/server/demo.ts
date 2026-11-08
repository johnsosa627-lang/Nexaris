/**
 * Datos de prueba para practicar con el sistema sin tocar empresas reales.
 * Todo lo que se crea acá queda marcado `isDemo` y se muestra con la etiqueta "PRUEBA".
 * Los nombres y dominios son inventados (dominios .example, que no existen).
 */
import { and, eq } from "drizzle-orm";
import { getDb } from "@/db";
import { activities, approvals, companies, contacts, followUps } from "@/db/schema";
import { writeAudit } from "./audit";
import { assertOwner, type Ctx } from "./context";
import { addActivity, addContact, addFollowUp, changeStage, createCompany } from "./crm";
import { UserError } from "./errors";
import { requestAction } from "./gateway";

const DEMO_COMPANIES = [
  { name: "Automotora Ejemplo Sur (PRUEBA)", website: "automotora-sur.example", city: "Montevideo", sector: "Automotoras", stage: "nuevo" },
  { name: "Inmobiliaria Ficticia Centro (PRUEBA)", website: "inmo-centro.example", city: "Montevideo", sector: "Inmobiliarias", stage: "contactado" },
  { name: "Tienda Online Inventada (PRUEBA)", website: "tienda-inventada.example", city: "Canelones", sector: "Tiendas online", stage: "respondio" },
  { name: "Distribuidora Demo Norte (PRUEBA)", website: "distribuidora-demo.example", city: "Salto", sector: "Distribuidores", stage: "reunion" },
  { name: "Servicios Simulados SRL (PRUEBA)", website: "servicios-simulados.example", city: "Maldonado", sector: "Empresas de servicios", stage: "cliente" },
] as const;

export async function loadDemoData(ctx: Ctx) {
  assertOwner(ctx);
  const [existing] = await getDb()
    .select({ id: companies.id })
    .from(companies)
    .where(and(eq(companies.workspaceId, ctx.workspaceId), eq(companies.isDemo, true)))
    .limit(1);
  if (existing) throw new UserError("Los datos de prueba ya están cargados.");

  const day = 24 * 3600_000;
  for (const [i, d] of DEMO_COMPANIES.entries()) {
    const c = await createCompany(
      ctx,
      {
        name: d.name,
        website: d.website,
        city: d.city,
        sector: d.sector,
        country: "UY",
        source: "demo",
        notes: "Empresa inventada para practicar. No existe.",
      },
      { isDemo: true },
    );
    const contact = await addContact(ctx, c.id, {
      name: `Contacto de prueba ${i + 1}`,
      roleTitle: "Gerente comercial",
      email: `contacto${i + 1}@${d.website}`,
      source: "otro",
    });
    await addActivity(ctx, c.id, {
      type: "nota",
      title: "Nota de prueba",
      body: "Ejemplo de nota interna. Estos datos son ficticios.",
      contactId: contact.id,
    });
    if (d.stage !== "nuevo") await changeStage(ctx, c.id, d.stage);
    await addFollowUp(ctx, c.id, {
      title: i % 2 === 0 ? "Llamar para presentar el diagnóstico" : "Enviar propuesta revisada",
      dueAt: new Date(Date.now() + (i - 1) * day),
      contactId: contact.id,
    });
    if (i === 1) {
      await requestAction({
        workspaceId: ctx.workspaceId,
        actor: { type: "agent", agentKey: "email_engine" },
        actionType: "enviar_correo_externo",
        summary: `PRUEBA: enviar correo de presentación a ${contact.email}`,
        payload: { para: contact.email, asunto: "Ejemplo de correo (prueba)" },
        companyId: c.id,
        isDemo: true,
      });
    }
  }
  await writeAudit({
    workspaceId: ctx.workspaceId,
    actorType: "user",
    actorId: ctx.userId,
    action: "datos_prueba.cargados",
    ip: ctx.ip,
  });
}

export async function clearDemoData(ctx: Ctx) {
  assertOwner(ctx);
  const db = getDb();
  await db.transaction(async (tx) => {
    const ws = ctx.workspaceId;
    await tx.delete(approvals).where(and(eq(approvals.workspaceId, ws), eq(approvals.isDemo, true)));
    await tx.delete(followUps).where(and(eq(followUps.workspaceId, ws), eq(followUps.isDemo, true)));
    await tx.delete(activities).where(and(eq(activities.workspaceId, ws), eq(activities.isDemo, true)));
    await tx.delete(contacts).where(and(eq(contacts.workspaceId, ws), eq(contacts.isDemo, true)));
    await tx.delete(companies).where(and(eq(companies.workspaceId, ws), eq(companies.isDemo, true)));
  });
  await writeAudit({
    workspaceId: ctx.workspaceId,
    actorType: "user",
    actorId: ctx.userId,
    action: "datos_prueba.borrados",
    ip: ctx.ip,
  });
}
