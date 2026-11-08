import { and, asc, count, desc, eq, gte, ilike, inArray, lt, or, sql, type SQL } from "drizzle-orm";
import { z } from "zod";
import { getDb } from "@/db";
import { activities, approvals, companies, contacts, followUps, users } from "@/db/schema";
import {
  CONTACT_SOURCES,
  MANUAL_ACTIVITY_TYPES,
  OPEN_OPPORTUNITY_STAGES,
  PROSPECT_STAGES,
  STAGES,
  type Stage,
} from "@/lib/catalog";
import { domainFromUrl, normalizeWebsite } from "@/lib/format";
import { t } from "@/i18n";
import { diff, writeAudit } from "./audit";
import { assertInternal, type Ctx } from "./context";
import { UserError } from "./errors";
import { addSuppression, areAutomationsPaused, isSuppressed } from "./security";

const optionalText = (max: number) =>
  z
    .string()
    .trim()
    .max(max)
    .optional()
    .nullable()
    .transform((v) => (v ? v : null));

// ---------- Empresas ----------

const companySchema = z.object({
  name: z.string().trim().min(2, "Escribí el nombre de la empresa.").max(200),
  website: optionalText(500),
  country: z
    .string()
    .trim()
    .toUpperCase()
    .regex(/^[A-Z]{2}$/, "El país debe ser un código de 2 letras (ej. UY).")
    .default("UY"),
  city: optionalText(120),
  sector: optionalText(120),
  notes: optionalText(5000),
  source: z.enum(["manual", "planilla", "google_places", "referido", "demo"]).default("manual"),
  sourceDetail: optionalText(500),
});
export type CompanyInput = z.input<typeof companySchema>;

function prepareCompany(input: CompanyInput) {
  const data = companySchema.parse(input);
  let website: string | null = null;
  let domain: string | null = null;
  if (data.website) {
    website = normalizeWebsite(data.website);
    domain = domainFromUrl(data.website);
    if (!website || !domain) throw new UserError("La dirección del sitio web no es válida (ej. empresa.com.uy).");
  }
  return { ...data, website, domain };
}

async function assertDomainFree(workspaceId: string, domain: string | null, exceptId?: string) {
  if (!domain) return;
  const [dup] = await getDb()
    .select({ id: companies.id, name: companies.name })
    .from(companies)
    .where(and(eq(companies.workspaceId, workspaceId), eq(companies.domain, domain)))
    .limit(1);
  if (dup && dup.id !== exceptId) {
    throw new UserError(`Ya existe una empresa con el sitio ${domain}: "${dup.name}".`);
  }
}

export async function createCompany(ctx: Ctx, input: CompanyInput, opts: { isDemo?: boolean } = {}) {
  assertInternal(ctx);
  const data = prepareCompany(input);
  await assertDomainFree(ctx.workspaceId, data.domain);
  const [row] = await getDb()
    .insert(companies)
    .values({ ...data, workspaceId: ctx.workspaceId, ownerUserId: ctx.userId, isDemo: opts.isDemo ?? false })
    .returning();
  await writeAudit({
    workspaceId: ctx.workspaceId,
    actorType: "user",
    actorId: ctx.userId,
    action: "empresa.creada",
    entityType: "empresa",
    entityId: row.id,
    details: { nombre: row.name, dominio: row.domain },
    ip: ctx.ip,
  });
  return row;
}

async function getOwnedCompany(ctx: Ctx, id: string) {
  if (!z.uuid().safeParse(id).success) throw new UserError("Empresa no encontrada.");
  const [row] = await getDb()
    .select()
    .from(companies)
    .where(and(eq(companies.id, id), eq(companies.workspaceId, ctx.workspaceId)))
    .limit(1);
  if (!row) throw new UserError("Empresa no encontrada.");
  return row;
}

export async function updateCompany(ctx: Ctx, id: string, input: CompanyInput) {
  assertInternal(ctx);
  const before = await getOwnedCompany(ctx, id);
  const data = prepareCompany({ ...input, source: before.source as CompanyInput["source"] });
  await assertDomainFree(ctx.workspaceId, data.domain, id);
  const editable = {
    name: data.name,
    website: data.website,
    domain: data.domain,
    country: data.country,
    city: data.city,
    sector: data.sector,
    notes: data.notes,
  };
  const changes = diff(before as unknown as Record<string, unknown>, editable);
  if (Object.keys(changes).length === 0) return before;
  const [row] = await getDb()
    .update(companies)
    .set({ ...editable, updatedAt: new Date() })
    .where(and(eq(companies.id, id), eq(companies.workspaceId, ctx.workspaceId)))
    .returning();
  await writeAudit({
    workspaceId: ctx.workspaceId,
    actorType: "user",
    actorId: ctx.userId,
    action: "empresa.editada",
    entityType: "empresa",
    entityId: id,
    details: { cambios: changes },
    ip: ctx.ip,
  });
  return row;
}

export async function changeStage(ctx: Ctx, id: string, stage: string) {
  assertInternal(ctx);
  if (!(STAGES as readonly string[]).includes(stage)) throw new UserError("Etapa desconocida.");
  const before = await getOwnedCompany(ctx, id);
  if (before.stage === stage) return before;
  const db = getDb();
  const [row] = await db
    .update(companies)
    .set({ stage, updatedAt: new Date() })
    .where(and(eq(companies.id, id), eq(companies.workspaceId, ctx.workspaceId)))
    .returning();
  const from = t.stages[before.stage as Stage] ?? before.stage;
  const to = t.stages[stage as Stage];
  await db.insert(activities).values({
    workspaceId: ctx.workspaceId,
    companyId: id,
    type: "cambio_etapa",
    title: `Etapa: ${from} → ${to}`,
    actorType: "user",
    actorId: ctx.userId,
    isDemo: before.isDemo,
  });
  await writeAudit({
    workspaceId: ctx.workspaceId,
    actorType: "user",
    actorId: ctx.userId,
    action: "empresa.etapa_cambiada",
    entityType: "empresa",
    entityId: id,
    details: { antes: before.stage, despues: stage },
    ip: ctx.ip,
  });
  return row;
}

export async function listCompanies(ctx: Ctx, filters: { q?: string; stage?: string; sort?: string } = {}) {
  assertInternal(ctx);
  const conds: SQL[] = [eq(companies.workspaceId, ctx.workspaceId)];
  if (filters.stage && (STAGES as readonly string[]).includes(filters.stage)) {
    conds.push(eq(companies.stage, filters.stage));
  }
  const q = filters.q?.trim();
  if (q) {
    const like = `%${q.replace(/[%_\\]/g, (c) => `\\${c}`)}%`;
    conds.push(
      or(
        ilike(companies.name, like),
        ilike(companies.domain, like),
        ilike(companies.city, like),
        ilike(companies.sector, like),
      )!,
    );
  }
  return getDb()
    .select()
    .from(companies)
    .where(and(...conds))
    .orderBy(
      ...(filters.sort === "puntuacion"
        ? [sql`${companies.opportunityScore} desc nulls last`, desc(companies.updatedAt)]
        : [desc(companies.updatedAt)]),
    )
    .limit(500);
}

export async function getCompanyDetail(ctx: Ctx, id: string) {
  assertInternal(ctx);
  const company = await getOwnedCompany(ctx, id);
  const db = getDb();
  const [contactRows, activityRows, followUpRows, people] = await Promise.all([
    db
      .select()
      .from(contacts)
      .where(and(eq(contacts.companyId, id), eq(contacts.workspaceId, ctx.workspaceId)))
      .orderBy(asc(contacts.createdAt)),
    db
      .select()
      .from(activities)
      .where(and(eq(activities.companyId, id), eq(activities.workspaceId, ctx.workspaceId)))
      .orderBy(desc(activities.occurredAt), desc(activities.createdAt))
      .limit(300),
    db
      .select()
      .from(followUps)
      .where(and(eq(followUps.companyId, id), eq(followUps.workspaceId, ctx.workspaceId)))
      .orderBy(asc(followUps.dueAt)),
    db.select({ id: users.id, name: users.name }).from(users).where(eq(users.workspaceId, ctx.workspaceId)),
  ]);
  const names = new Map(people.map((p) => [p.id, p.name]));
  const now = new Date();
  const suppressed = await Promise.all(
    contactRows.map(async (c) => (c.email ? isSuppressed(ctx.workspaceId, c.email) : false)),
  );
  return {
    company,
    contacts: contactRows.map((c, i) => ({ ...c, suppressed: suppressed[i] || c.optedOut })),
    activities: activityRows.map((a) => ({
      ...a,
      actorName:
        a.actorType === "user" ? (names.get(a.actorId ?? "") ?? "Usuario") : a.actorType === "agent" ? a.actorId : "Sistema",
    })),
    followUps: followUpRows.map((f) => ({ ...f, overdue: f.status === "pendiente" && f.dueAt < now })),
    /** Sugerencia para un nuevo seguimiento: mañana a las 10:00 (Montevideo). */
    suggestedDueAt: suggestedDueAt(now),
  };
}

// ---------- Contactos ----------

const contactSchema = z
  .object({
    name: z.string().trim().min(2, "Escribí el nombre del contacto.").max(200),
    roleTitle: optionalText(200),
    email: z
      .string()
      .trim()
      .toLowerCase()
      .max(320)
      .optional()
      .nullable()
      .transform((v) => (v ? v : null))
      .refine((v) => v === null || z.email().safeParse(v).success, "El email no es válido."),
    phone: optionalText(60),
    source: z
      .enum(CONTACT_SOURCES)
      .optional()
      .nullable()
      .transform((v) => v ?? null),
    sourceUrl: optionalText(1000).refine(
      (v) => v === null || /^https?:\/\//i.test(v),
      "La URL de origen debe empezar con http:// o https://",
    ),
  })
  .refine((c) => !(c.email || c.phone) || c.source, {
    message: "Indicá de dónde salió el email o teléfono. No se cargan datos de contacto sin origen.",
    path: ["source"],
  });
export type ContactInput = z.input<typeof contactSchema>;

export async function addContact(ctx: Ctx, companyId: string, input: ContactInput) {
  assertInternal(ctx);
  const company = await getOwnedCompany(ctx, companyId);
  const data = contactSchema.parse(input);
  const [row] = await getDb()
    .insert(contacts)
    .values({ ...data, workspaceId: ctx.workspaceId, companyId, isDemo: company.isDemo })
    .returning();
  await writeAudit({
    workspaceId: ctx.workspaceId,
    actorType: "user",
    actorId: ctx.userId,
    action: "contacto.creado",
    entityType: "contacto",
    entityId: row.id,
    details: { empresa: companyId, origen: data.source, urlOrigen: data.sourceUrl },
    ip: ctx.ip,
  });
  return row;
}

/** La persona pidió no recibir más mensajes: se marca y su email va a la lista de exclusión. */
export async function optOutContact(ctx: Ctx, contactId: string) {
  assertInternal(ctx);
  if (!z.uuid().safeParse(contactId).success) throw new UserError("Contacto no encontrado.");
  const db = getDb();
  const [c] = await db
    .select()
    .from(contacts)
    .where(and(eq(contacts.id, contactId), eq(contacts.workspaceId, ctx.workspaceId)))
    .limit(1);
  if (!c) throw new UserError("Contacto no encontrado.");
  await db.update(contacts).set({ optedOut: true, optedOutAt: new Date() }).where(eq(contacts.id, c.id));
  if (c.email) await addSuppression(ctx, c.email, `Baja pedida por ${c.name}`);
  await db.insert(activities).values({
    workspaceId: ctx.workspaceId,
    companyId: c.companyId,
    contactId: c.id,
    type: "sistema",
    title: `${c.name} pidió no recibir más mensajes (baja registrada)`,
    actorType: "user",
    actorId: ctx.userId,
    isDemo: c.isDemo,
  });
  await writeAudit({
    workspaceId: ctx.workspaceId,
    actorType: "user",
    actorId: ctx.userId,
    action: "contacto.baja",
    entityType: "contacto",
    entityId: c.id,
    ip: ctx.ip,
  });
}

// ---------- Actividad ----------

const activitySchema = z.object({
  type: z.enum(MANUAL_ACTIVITY_TYPES as [string, ...string[]], { message: "Tipo de actividad inválido." }),
  title: z.string().trim().min(2, "Escribí un título corto.").max(300),
  body: optionalText(10000),
  occurredAt: z.coerce.date().optional(),
  contactId: z
    .string()
    .optional()
    .nullable()
    .transform((v) => (v ? v : null)),
});
export type ActivityInput = z.input<typeof activitySchema>;

export async function addActivity(ctx: Ctx, companyId: string, input: ActivityInput) {
  assertInternal(ctx);
  const company = await getOwnedCompany(ctx, companyId);
  const data = activitySchema.parse(input);
  if (data.occurredAt && data.occurredAt.getTime() > Date.now() + 5 * 60_000) {
    throw new UserError("La fecha de una actividad no puede ser futura. Para algo futuro creá un seguimiento.");
  }
  if (data.contactId) await assertContactInCompany(ctx, data.contactId, companyId);
  const [row] = await getDb()
    .insert(activities)
    .values({
      workspaceId: ctx.workspaceId,
      companyId,
      contactId: data.contactId,
      type: data.type,
      title: data.title,
      body: data.body,
      occurredAt: data.occurredAt ?? new Date(),
      actorType: "user",
      actorId: ctx.userId,
      isDemo: company.isDemo,
    })
    .returning();
  await getDb().update(companies).set({ updatedAt: new Date() }).where(eq(companies.id, companyId));
  return row;
}

async function assertContactInCompany(ctx: Ctx, contactId: string, companyId: string) {
  if (!z.uuid().safeParse(contactId).success) throw new UserError("Contacto no encontrado.");
  const [c] = await getDb()
    .select({ id: contacts.id })
    .from(contacts)
    .where(
      and(eq(contacts.id, contactId), eq(contacts.companyId, companyId), eq(contacts.workspaceId, ctx.workspaceId)),
    )
    .limit(1);
  if (!c) throw new UserError("Ese contacto no pertenece a esta empresa.");
}

// ---------- Seguimientos ----------

const followUpSchema = z.object({
  title: z.string().trim().min(2, "Escribí qué hay que hacer.").max(300),
  dueAt: z.coerce.date({ message: "Elegí una fecha." }),
  contactId: z
    .string()
    .optional()
    .nullable()
    .transform((v) => (v ? v : null)),
});
export type FollowUpInput = z.input<typeof followUpSchema>;

export async function addFollowUp(ctx: Ctx, companyId: string, input: FollowUpInput) {
  assertInternal(ctx);
  const company = await getOwnedCompany(ctx, companyId);
  const data = followUpSchema.parse(input);
  if (Number.isNaN(data.dueAt.getTime())) throw new UserError("Elegí una fecha válida.");
  if (data.contactId) await assertContactInCompany(ctx, data.contactId, companyId);
  const [row] = await getDb()
    .insert(followUps)
    .values({
      workspaceId: ctx.workspaceId,
      companyId,
      contactId: data.contactId,
      title: data.title,
      dueAt: data.dueAt,
      assignedUserId: ctx.userId,
      createdBy: ctx.userId,
      isDemo: company.isDemo,
    })
    .returning();
  await writeAudit({
    workspaceId: ctx.workspaceId,
    actorType: "user",
    actorId: ctx.userId,
    action: "seguimiento.creado",
    entityType: "seguimiento",
    entityId: row.id,
    details: { empresa: companyId, fecha: data.dueAt.toISOString() },
    ip: ctx.ip,
  });
  return row;
}

export async function setFollowUpStatus(ctx: Ctx, id: string, status: "hecho" | "cancelado") {
  assertInternal(ctx);
  if (!z.uuid().safeParse(id).success) throw new UserError("Seguimiento no encontrado.");
  const db = getDb();
  const [row] = await db
    .update(followUps)
    .set({ status, completedAt: new Date() })
    .where(and(eq(followUps.id, id), eq(followUps.workspaceId, ctx.workspaceId), eq(followUps.status, "pendiente")))
    .returning();
  if (!row) throw new UserError("El seguimiento no existe o ya estaba cerrado.");
  await db.insert(activities).values({
    workspaceId: ctx.workspaceId,
    companyId: row.companyId,
    contactId: row.contactId,
    type: "seguimiento",
    title: `Seguimiento ${status === "hecho" ? "realizado" : "cancelado"}: ${row.title}`,
    actorType: "user",
    actorId: ctx.userId,
    isDemo: row.isDemo,
  });
  return row;
}

function suggestedDueAt(now: Date): Date {
  const d = new Date(now.getTime() + 24 * 3600_000);
  d.setUTCHours(13, 0, 0, 0); // 10:00 en Montevideo (UTC-3)
  return d;
}

export async function listFollowUps(ctx: Ctx, opts: { status?: "pendiente" | "hecho" | "cancelado" } = {}) {
  assertInternal(ctx);
  const now = new Date();
  const rows = await getDb()
    .select({ followUp: followUps, companyName: companies.name, companyId: companies.id })
    .from(followUps)
    .innerJoin(companies, eq(companies.id, followUps.companyId))
    .where(and(eq(followUps.workspaceId, ctx.workspaceId), eq(followUps.status, opts.status ?? "pendiente")))
    .orderBy(asc(followUps.dueAt))
    .limit(500);
  return rows.map((r) => ({ ...r, overdue: r.followUp.status === "pendiente" && r.followUp.dueAt < now }));
}

// ---------- Panel principal ----------

export async function getDashboard(ctx: Ctx) {
  assertInternal(ctx);
  const db = getDb();
  const ws = ctx.workspaceId;
  const now = new Date();
  const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 3600_000);

  const n = async (where: SQL | undefined, table: typeof companies | typeof followUps | typeof approvals) => {
    const [row] = await db.select({ n: count() }).from(table).where(where);
    return Number(row.n);
  };

  const [
    activeClients,
    newProspects,
    openOpportunities,
    pendingFollowUps,
    overdueFollowUps,
    pendingApprovals,
    totalCompanies,
    demoCompanies,
    stageRows,
    recentActivity,
    upcoming,
    paused,
  ] = await Promise.all([
    n(and(eq(companies.workspaceId, ws), eq(companies.stage, "cliente")), companies),
    n(
      and(
        eq(companies.workspaceId, ws),
        inArray(companies.stage, PROSPECT_STAGES),
        gte(companies.createdAt, thirtyDaysAgo),
      ),
      companies,
    ),
    n(and(eq(companies.workspaceId, ws), inArray(companies.stage, OPEN_OPPORTUNITY_STAGES)), companies),
    n(and(eq(followUps.workspaceId, ws), eq(followUps.status, "pendiente")), followUps),
    n(and(eq(followUps.workspaceId, ws), eq(followUps.status, "pendiente"), lt(followUps.dueAt, now)), followUps),
    n(and(eq(approvals.workspaceId, ws), eq(approvals.status, "pendiente")), approvals),
    n(eq(companies.workspaceId, ws), companies),
    n(and(eq(companies.workspaceId, ws), eq(companies.isDemo, true)), companies),
    db
      .select({ stage: companies.stage, n: count() })
      .from(companies)
      .where(eq(companies.workspaceId, ws))
      .groupBy(companies.stage),
    db
      .select({ activity: activities, companyName: companies.name })
      .from(activities)
      .innerJoin(companies, eq(companies.id, activities.companyId))
      .where(eq(activities.workspaceId, ws))
      .orderBy(desc(activities.occurredAt))
      .limit(8),
    db
      .select({ followUp: followUps, companyName: companies.name })
      .from(followUps)
      .innerJoin(companies, eq(companies.id, followUps.companyId))
      .where(and(eq(followUps.workspaceId, ws), eq(followUps.status, "pendiente")))
      .orderBy(asc(followUps.dueAt))
      .limit(6),
    areAutomationsPaused(ws),
  ]);

  const byStage = Object.fromEntries(STAGES.map((s) => [s, 0])) as Record<Stage, number>;
  for (const r of stageRows) byStage[r.stage as Stage] = Number(r.n);

  const alerts: { kind: "danger" | "warning" | "info"; text: string; href?: string }[] = [];
  if (paused) alerts.push({ kind: "danger", text: "Las automatizaciones están detenidas.", href: "/seguridad" });
  if (overdueFollowUps > 0) {
    alerts.push({
      kind: "warning",
      text: `${overdueFollowUps} seguimiento(s) vencido(s).`,
      href: "/seguimientos",
    });
  }
  if (pendingApprovals > 0) {
    alerts.push({ kind: "warning", text: `${pendingApprovals} acción(es) esperando tu aprobación.`, href: "/aprobaciones" });
  }
  if (demoCompanies > 0) {
    alerts.push({
      kind: "info",
      text: `Hay ${demoCompanies} empresa(s) de prueba. Sus datos no son reales.`,
      href: "/seguridad#datos-prueba",
    });
  }

  return {
    activeClients,
    newProspects,
    openOpportunities,
    pendingFollowUps,
    overdueFollowUps,
    pendingApprovals,
    totalCompanies,
    demoCompanies,
    byStage,
    recentActivity,
    upcoming: upcoming.map((u) => ({ ...u, overdue: u.followUp.dueAt < now })),
    paused,
    alerts,
  };
}
