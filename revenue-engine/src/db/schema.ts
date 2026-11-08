/**
 * Esquema de la base de datos de Revenue Engine AI.
 *
 * Reglas de diseño:
 * - Toda tabla con datos de negocio lleva `workspaceId`: es la frontera de separación de datos.
 *   Las funciones de `src/server/` siempre filtran por ese campo.
 * - Los valores que el sistema puede cambiar con el tiempo se guardan como texto validado en
 *   TypeScript (no como enums de PostgreSQL) para poder agregar valores sin migraciones riesgosas.
 * - `isDemo` marca los datos de prueba: se muestran con una etiqueta y se pueden borrar de una vez.
 * - El registro de actividad (`auditLog`) es de solo escritura: no hay funciones que lo editen o borren.
 */
import { sql } from "drizzle-orm";
import {
  bigserial,
  boolean,
  index,
  integer,
  jsonb,
  pgTable,
  primaryKey,
  text,
  timestamp,
  uniqueIndex,
  uuid,
} from "drizzle-orm/pg-core";

const createdAt = () => timestamp("created_at", { withTimezone: true }).notNull().defaultNow();
const updatedAt = () => timestamp("updated_at", { withTimezone: true }).notNull().defaultNow();

/** Espacio de trabajo: tu negocio (la agencia). Más adelante podría haber varios. */
export const workspaces = pgTable("workspaces", {
  id: uuid("id").primaryKey().defaultRandom(),
  name: text("name").notNull(),
  country: text("country").notNull().default("UY"),
  defaultCurrency: text("default_currency").notNull().default("USD"),
  locale: text("locale").notNull().default("es"),
  timezone: text("timezone").notNull().default("America/Montevideo"),
  // Botón para detener automatizaciones
  automationsPaused: boolean("automations_paused").notNull().default(false),
  pausedAt: timestamp("paused_at", { withTimezone: true }),
  pausedBy: uuid("paused_by"),
  pausedReason: text("paused_reason"),
  // Límites de gasto (en centavos de dólar)
  aiMonthlyBudgetCents: integer("ai_monthly_budget_cents").notNull().default(3000),
  maxSpendPerActionCents: integer("max_spend_per_action_cents").notNull().default(0),
  dailyEmailLimit: integer("daily_email_limit").notNull().default(20),
  createdAt: createdAt(),
});

export const users = pgTable(
  "users",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    workspaceId: uuid("workspace_id")
      .notNull()
      .references(() => workspaces.id),
    email: text("email").notNull(),
    name: text("name").notNull(),
    passwordHash: text("password_hash").notNull(),
    /** owner = dueño · team = equipo · client = usuario del portal de una empresa cliente */
    role: text("role").notNull(),
    /** Solo para usuarios del portal: la única empresa que pueden ver. */
    companyId: uuid("company_id"),
    active: boolean("active").notNull().default(true),
    lastLoginAt: timestamp("last_login_at", { withTimezone: true }),
    createdAt: createdAt(),
  },
  (t) => [uniqueIndex("users_email_unique").on(t.email)],
);

export const sessions = pgTable(
  "sessions",
  {
    /** Hash SHA-256 del token. El token real solo existe en la cookie del navegador. */
    id: text("id").primaryKey(),
    userId: uuid("user_id")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    expiresAt: timestamp("expires_at", { withTimezone: true }).notNull(),
    ip: text("ip"),
    userAgent: text("user_agent"),
    createdAt: createdAt(),
  },
  (t) => [index("sessions_user_idx").on(t.userId)],
);

export const companies = pgTable(
  "companies",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    workspaceId: uuid("workspace_id")
      .notNull()
      .references(() => workspaces.id),
    name: text("name").notNull(),
    website: text("website"),
    /** Dominio normalizado (sin www): evita cargar dos veces la misma empresa. */
    domain: text("domain"),
    country: text("country").notNull().default("UY"),
    city: text("city"),
    sector: text("sector"),
    stage: text("stage").notNull().default("nuevo"),
    source: text("source").notNull().default("manual"),
    sourceDetail: text("source_detail"),
    ownerUserId: uuid("owner_user_id").references(() => users.id),
    /** Puntuación de oportunidad 0-100. Se calcula en la Etapa 1B; null = sin calcular. */
    opportunityScore: integer("opportunity_score"),
    notes: text("notes"),
    isDemo: boolean("is_demo").notNull().default(false),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (t) => [
    index("companies_workspace_idx").on(t.workspaceId, t.stage),
    uniqueIndex("companies_workspace_domain_unique")
      .on(t.workspaceId, t.domain)
      .where(sql`${t.domain} is not null`),
  ],
);

export const contacts = pgTable(
  "contacts",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    workspaceId: uuid("workspace_id")
      .notNull()
      .references(() => workspaces.id),
    companyId: uuid("company_id")
      .notNull()
      .references(() => companies.id, { onDelete: "cascade" }),
    name: text("name").notNull(),
    roleTitle: text("role_title"),
    email: text("email"),
    phone: text("phone"),
    /** De dónde salió el dato. Obligatorio si hay email o teléfono: no se inventan contactos. */
    source: text("source"),
    sourceUrl: text("source_url"),
    optedOut: boolean("opted_out").notNull().default(false),
    optedOutAt: timestamp("opted_out_at", { withTimezone: true }),
    isDemo: boolean("is_demo").notNull().default(false),
    createdAt: createdAt(),
  },
  (t) => [index("contacts_company_idx").on(t.companyId)],
);

export const activities = pgTable(
  "activities",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    workspaceId: uuid("workspace_id")
      .notNull()
      .references(() => workspaces.id),
    companyId: uuid("company_id")
      .notNull()
      .references(() => companies.id, { onDelete: "cascade" }),
    contactId: uuid("contact_id").references(() => contacts.id, { onDelete: "set null" }),
    type: text("type").notNull(),
    title: text("title").notNull(),
    body: text("body"),
    occurredAt: timestamp("occurred_at", { withTimezone: true }).notNull().defaultNow(),
    actorType: text("actor_type").notNull(),
    actorId: text("actor_id"),
    isDemo: boolean("is_demo").notNull().default(false),
    createdAt: createdAt(),
  },
  (t) => [index("activities_company_idx").on(t.companyId, t.occurredAt)],
);

export const followUps = pgTable(
  "follow_ups",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    workspaceId: uuid("workspace_id")
      .notNull()
      .references(() => workspaces.id),
    companyId: uuid("company_id")
      .notNull()
      .references(() => companies.id, { onDelete: "cascade" }),
    contactId: uuid("contact_id").references(() => contacts.id, { onDelete: "set null" }),
    title: text("title").notNull(),
    dueAt: timestamp("due_at", { withTimezone: true }).notNull(),
    status: text("status").notNull().default("pendiente"),
    assignedUserId: uuid("assigned_user_id").references(() => users.id),
    createdBy: uuid("created_by").references(() => users.id),
    completedAt: timestamp("completed_at", { withTimezone: true }),
    isDemo: boolean("is_demo").notNull().default(false),
    createdAt: createdAt(),
  },
  (t) => [index("follow_ups_due_idx").on(t.workspaceId, t.status, t.dueAt)],
);

/** Ajustes de cada agente. El catálogo (qué agentes existen) vive en el código. */
export const agentSettings = pgTable(
  "agent_settings",
  {
    workspaceId: uuid("workspace_id")
      .notNull()
      .references(() => workspaces.id),
    agentKey: text("agent_key").notNull(),
    enabled: boolean("enabled").notNull().default(false),
    model: text("model").notNull(),
    monthlyBudgetCents: integer("monthly_budget_cents").notNull().default(0),
    instructions: text("instructions"),
    updatedAt: updatedAt(),
  },
  (t) => [primaryKey({ columns: [t.workspaceId, t.agentKey] })],
);

/** Nivel de autonomía elegido para cada tipo de acción. Nunca puede ser menor al mínimo del código. */
export const actionPolicies = pgTable(
  "action_policies",
  {
    workspaceId: uuid("workspace_id")
      .notNull()
      .references(() => workspaces.id),
    actionType: text("action_type").notNull(),
    level: integer("level").notNull(),
    updatedBy: uuid("updated_by").references(() => users.id),
    updatedAt: updatedAt(),
  },
  (t) => [primaryKey({ columns: [t.workspaceId, t.actionType] })],
);

/** Cola de aprobaciones: acciones de nivel 2 y 3 esperando una decisión humana. */
export const approvals = pgTable(
  "approvals",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    workspaceId: uuid("workspace_id")
      .notNull()
      .references(() => workspaces.id),
    actionType: text("action_type").notNull(),
    level: integer("level").notNull(),
    status: text("status").notNull().default("pendiente"),
    summary: text("summary").notNull(),
    payload: jsonb("payload").notNull().default({}),
    companyId: uuid("company_id").references(() => companies.id, { onDelete: "set null" }),
    requestedByType: text("requested_by_type").notNull(),
    requestedById: text("requested_by_id"),
    decidedBy: uuid("decided_by").references(() => users.id),
    decidedAt: timestamp("decided_at", { withTimezone: true }),
    decisionNote: text("decision_note"),
    result: jsonb("result"),
    isDemo: boolean("is_demo").notNull().default(false),
    createdAt: createdAt(),
  },
  (t) => [index("approvals_status_idx").on(t.workspaceId, t.status)],
);

/** Lista de exclusión: emails o dominios a los que nunca se les escribe. */
export const suppressionList = pgTable(
  "suppression_list",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    workspaceId: uuid("workspace_id")
      .notNull()
      .references(() => workspaces.id),
    value: text("value").notNull(),
    kind: text("kind").notNull(),
    reason: text("reason"),
    createdBy: uuid("created_by").references(() => users.id),
    createdAt: createdAt(),
  },
  (t) => [uniqueIndex("suppression_unique").on(t.workspaceId, t.value)],
);

/** Registro de actividad: quién hizo qué y cuándo. Solo se agregan filas. */
export const auditLog = pgTable(
  "audit_log",
  {
    id: bigserial("id", { mode: "number" }).primaryKey(),
    workspaceId: uuid("workspace_id"),
    at: timestamp("at", { withTimezone: true }).notNull().defaultNow(),
    actorType: text("actor_type").notNull(),
    actorId: text("actor_id"),
    action: text("action").notNull(),
    entityType: text("entity_type"),
    entityId: text("entity_id"),
    details: jsonb("details"),
    ip: text("ip"),
  },
  (t) => [
    index("audit_workspace_idx").on(t.workspaceId, t.at),
    index("audit_action_idx").on(t.action, t.at),
  ],
);

// ---------------------------------------------------------------------------
// Etapa 1B: diagnósticos
// ---------------------------------------------------------------------------

/** Un análisis de la presencia digital de una empresa. */
export const diagnoses = pgTable(
  "diagnoses",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    workspaceId: uuid("workspace_id")
      .notNull()
      .references(() => workspaces.id),
    companyId: uuid("company_id")
      .notNull()
      .references(() => companies.id, { onDelete: "cascade" }),
    /** en_cola · en_proceso · listo · fallido */
    status: text("status").notNull().default("en_cola"),
    attempts: integer("attempts").notNull().default(0),
    requestedBy: uuid("requested_by").references(() => users.id),
    analyzedUrl: text("analyzed_url"),
    /** Hechos medidos en el sitio (ver src/server/analyzer/types.ts). */
    facts: jsonb("facts"),
    score: integer("score"),
    scoreBreakdown: jsonb("score_breakdown"),
    /** Resumen redactado por la IA (null si no se usó IA). */
    aiSummary: jsonb("ai_summary"),
    /** Por qué no hay resumen de IA, si no lo hay (sin clave, tope de gasto, etc.). */
    aiNote: text("ai_note"),
    model: text("model"),
    costCents: integer("cost_cents").notNull().default(0),
    error: text("error"),
    isDemo: boolean("is_demo").notNull().default(false),
    createdAt: createdAt(),
    startedAt: timestamp("started_at", { withTimezone: true }),
    finishedAt: timestamp("finished_at", { withTimezone: true }),
  },
  (t) => [
    index("diagnoses_company_idx").on(t.companyId, t.createdAt),
    index("diagnoses_status_idx").on(t.status, t.createdAt),
  ],
);

/** Cada problema u observación encontrada. kind: hecho (medido) · estimacion · hipotesis. */
export const findings = pgTable(
  "findings",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    workspaceId: uuid("workspace_id")
      .notNull()
      .references(() => workspaces.id),
    diagnosisId: uuid("diagnosis_id")
      .notNull()
      .references(() => diagnoses.id, { onDelete: "cascade" }),
    companyId: uuid("company_id")
      .notNull()
      .references(() => companies.id, { onDelete: "cascade" }),
    code: text("code").notNull(),
    kind: text("kind").notNull(),
    category: text("category").notNull(),
    severity: text("severity").notNull(),
    title: text("title").notNull(),
    detail: text("detail").notNull(),
    evidence: text("evidence"),
    sourceUrl: text("source_url"),
    recommendation: text("recommendation"),
    service: text("service"),
    createdAt: createdAt(),
  },
  (t) => [index("findings_diagnosis_idx").on(t.diagnosisId)],
);

/** Cada llamada a un modelo de IA: para controlar el gasto real. */
export const aiUsage = pgTable(
  "ai_usage",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    workspaceId: uuid("workspace_id")
      .notNull()
      .references(() => workspaces.id),
    agentKey: text("agent_key").notNull(),
    model: text("model").notNull(),
    purpose: text("purpose").notNull(),
    inputTokens: integer("input_tokens").notNull().default(0),
    outputTokens: integer("output_tokens").notNull().default(0),
    /** Costo en milésimas de centavo de dólar (1 = US$0,00001) para no perder precisión. */
    costMillicents: integer("cost_millicents").notNull().default(0),
    diagnosisId: uuid("diagnosis_id").references(() => diagnoses.id, { onDelete: "set null" }),
    createdAt: createdAt(),
  },
  (t) => [index("ai_usage_workspace_idx").on(t.workspaceId, t.createdAt)],
);
