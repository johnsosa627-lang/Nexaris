/**
 * Catálogos fijos del sistema. Viven en el código (no en la base de datos) para que nadie pueda,
 * por ejemplo, bajar el nivel de seguridad mínimo de una acción desde la base de datos.
 * Los textos visibles están en `src/i18n/`.
 */

// ---------- CRM ----------

export const STAGES = [
  "nuevo",
  "investigado",
  "contactado",
  "respondio",
  "reunion",
  "propuesta",
  "negociacion",
  "cliente",
  "perdido",
  "descartado",
] as const;
export type Stage = (typeof STAGES)[number];

/** Etapas que cuentan como "oportunidad abierta" en el panel. */
export const OPEN_OPPORTUNITY_STAGES: Stage[] = ["respondio", "reunion", "propuesta", "negociacion"];
export const PROSPECT_STAGES: Stage[] = ["nuevo", "investigado", "contactado"];

export const ACTIVITY_TYPES = [
  "nota",
  "llamada",
  "reunion",
  "correo_enviado",
  "correo_recibido",
  "cambio_etapa",
  "seguimiento",
  "sistema",
] as const;
export type ActivityType = (typeof ACTIVITY_TYPES)[number];
/** Tipos que una persona puede registrar a mano (los demás los genera el sistema). */
export const MANUAL_ACTIVITY_TYPES: ActivityType[] = [
  "nota",
  "llamada",
  "reunion",
  "correo_enviado",
  "correo_recibido",
];

export const CONTACT_SOURCES = [
  "sitio_web_empresa",
  "ficha_publica",
  "el_contacto_lo_dio",
  "reunion_o_evento",
  "referido",
  "otro",
] as const;
export type ContactSource = (typeof CONTACT_SOURCES)[number];

export const COMPANY_SOURCES = ["manual", "planilla", "google_places", "referido", "demo"] as const;

export const ROLES = ["owner", "team", "client"] as const;
export type Role = (typeof ROLES)[number];

// ---------- Autonomía y seguridad ----------

export type Level = 1 | 2 | 3;

export const ACTION_TYPES = {
  // Nivel 1: automático
  analizar_datos: { minLevel: 1 },
  investigar: { minLevel: 1 },
  preparar_diagnostico: { minLevel: 1 },
  crear_borrador: { minLevel: 1 },
  generar_informe: { minLevel: 1 },
  detectar_oportunidades: { minLevel: 1 },
  // Nivel 2: requiere aprobación
  enviar_correo_externo: { minLevel: 2 },
  publicar_contenido: { minLevel: 2 },
  cambiar_precios: { minLevel: 2 },
  lanzar_campana: { minLevel: 2 },
  modificar_presupuesto: { minLevel: 2 },
  contactar_cliente: { minLevel: 2 },
  // Nivel 3: restringidas
  gastar_dinero: { minLevel: 3 },
  firmar_contrato: { minLevel: 3 },
  realizar_pago: { minLevel: 3 },
  acceder_finanzas_sensibles: { minLevel: 3 },
  accion_legal_o_irreversible: { minLevel: 3 },
} as const satisfies Record<string, { minLevel: Level }>;

export type ActionType = keyof typeof ACTION_TYPES;

export function isActionType(value: string): value is ActionType {
  return Object.prototype.hasOwnProperty.call(ACTION_TYPES, value);
}

export const APPROVAL_STATUSES = [
  "pendiente",
  "aprobada",
  "rechazada",
  "ejecutada",
  "fallida",
  "bloqueada",
] as const;
export type ApprovalStatus = (typeof APPROVAL_STATUSES)[number];

// ---------- Agentes ----------

export const AI_MODELS = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"] as const;
export type AiModel = (typeof AI_MODELS)[number];

/** Precios de la API en US$ por millón de tokens (entrada / salida). Revisar si Anthropic los cambia. */
export const MODEL_PRICES: Record<AiModel, { input: number; output: number }> = {
  "claude-opus-5-5": { input: 4, output: 20 },
  "claude-sonnet-5-5": { input: 2, output: 10 },
  "claude-haiku-5-5": { input: 0.1, output: 0.5 },
};

export type AgentDefinition = {
  key: string;
  /** Fase del plan en la que el agente empieza a funcionar de verdad. */
  phase: number;
  defaultModel: AiModel;
  /** Acciones que este agente puede solicitar. Todas pasan por el portero de acciones. */
  actions: ActionType[];
};

export const AGENTS: AgentDefinition[] = [
  {
    key: "director",
    phase: 1,
    defaultModel: "claude-opus-5-5",
    actions: ["analizar_datos", "preparar_diagnostico", "detectar_oportunidades", "generar_informe", "crear_borrador"],
  },
  {
    key: "market_research",
    phase: 3,
    defaultModel: "claude-sonnet-5-5",
    actions: ["investigar", "analizar_datos"],
  },
  {
    key: "competitor_intelligence",
    phase: 3,
    defaultModel: "claude-sonnet-5-5",
    actions: ["investigar", "analizar_datos"],
  },
  {
    key: "product_intelligence",
    phase: 3,
    defaultModel: "claude-sonnet-5-5",
    actions: ["investigar", "analizar_datos", "cambiar_precios"],
  },
  {
    key: "seo_engine",
    phase: 3,
    defaultModel: "claude-sonnet-5-5",
    actions: ["analizar_datos", "crear_borrador", "publicar_contenido"],
  },
  {
    key: "conversion_engine",
    phase: 3,
    defaultModel: "claude-opus-5-5",
    actions: ["analizar_datos", "preparar_diagnostico", "crear_borrador"],
  },
  {
    key: "creative_engine",
    phase: 6,
    defaultModel: "claude-sonnet-5-5",
    actions: ["crear_borrador", "publicar_contenido"],
  },
  {
    key: "advertising_engine",
    phase: 6,
    defaultModel: "claude-opus-5-5",
    actions: ["analizar_datos", "lanzar_campana", "modificar_presupuesto", "gastar_dinero"],
  },
  {
    key: "sales_engine",
    phase: 2,
    defaultModel: "claude-sonnet-5-5",
    actions: ["analizar_datos", "crear_borrador", "contactar_cliente"],
  },
  {
    key: "email_engine",
    phase: 2,
    defaultModel: "claude-opus-5-5",
    actions: ["investigar", "crear_borrador", "enviar_correo_externo"],
  },
  {
    key: "customer_recovery",
    phase: 6,
    defaultModel: "claude-sonnet-5-5",
    actions: ["detectar_oportunidades", "crear_borrador", "contactar_cliente"],
  },
  {
    key: "financial_intelligence",
    phase: 5,
    defaultModel: "claude-opus-5-5",
    actions: ["analizar_datos", "generar_informe", "acceder_finanzas_sensibles"],
  },
  {
    key: "customer_experience",
    phase: 3,
    defaultModel: "claude-haiku-5-5",
    actions: ["analizar_datos", "detectar_oportunidades", "crear_borrador"],
  },
];

export function getAgent(key: string): AgentDefinition | undefined {
  return AGENTS.find((a) => a.key === key);
}
