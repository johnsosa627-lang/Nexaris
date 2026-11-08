/**
 * Textos en español. Para agregar otro idioma: copiar este archivo (ej. `pt.ts`),
 * traducir los valores y registrarlo en `src/i18n/index.ts`.
 */
export const es = {
  app: {
    name: "Revenue Engine AI",
    tagline: "Inteligencia comercial para captar empresas y medir resultados",
  },
  nav: {
    panel: "Panel",
    empresas: "Empresas",
    seguimientos: "Seguimientos",
    aprobaciones: "Aprobaciones",
    agentes: "Agentes",
    seguridad: "Seguridad",
    salir: "Salir",
  },
  roles: { owner: "Dueño", team: "Equipo", client: "Cliente" },
  stages: {
    nuevo: "Nuevo",
    investigado: "Investigado",
    contactado: "Contactado",
    respondio: "Respondió",
    reunion: "Reunión",
    propuesta: "Propuesta enviada",
    negociacion: "Negociación",
    cliente: "Cliente activo",
    perdido: "Perdido",
    descartado: "Descartado",
  },
  activityTypes: {
    nota: "Nota",
    llamada: "Llamada",
    reunion: "Reunión",
    correo_enviado: "Correo enviado",
    correo_recibido: "Correo recibido",
    cambio_etapa: "Cambio de etapa",
    seguimiento: "Seguimiento",
    sistema: "Sistema",
  },
  contactSources: {
    sitio_web_empresa: "Publicado en el sitio web de la empresa",
    ficha_publica: "Ficha pública (Google, directorio, red social de la empresa)",
    el_contacto_lo_dio: "La persona me lo dio",
    reunion_o_evento: "Reunión o evento",
    referido: "Me lo pasó un referido",
    otro: "Otro (explicar en la URL o nota)",
  },
  companySources: {
    manual: "Carga manual",
    planilla: "Planilla",
    google_places: "Google Places",
    referido: "Referido",
    demo: "Datos de prueba",
  },
  levels: {
    1: "Nivel 1 · Automático",
    2: "Nivel 2 · Requiere aprobación",
    3: "Nivel 3 · Restringida",
  },
  actionTypes: {
    analizar_datos: "Analizar datos",
    investigar: "Investigar",
    preparar_diagnostico: "Preparar diagnósticos",
    crear_borrador: "Crear borradores",
    generar_informe: "Generar informes",
    detectar_oportunidades: "Detectar oportunidades",
    enviar_correo_externo: "Enviar correos externos",
    publicar_contenido: "Publicar contenidos",
    cambiar_precios: "Cambiar precios",
    lanzar_campana: "Lanzar campañas",
    modificar_presupuesto: "Modificar presupuestos",
    contactar_cliente: "Contactar clientes",
    gastar_dinero: "Gastar dinero",
    firmar_contrato: "Firmar contratos",
    realizar_pago: "Realizar pagos",
    acceder_finanzas_sensibles: "Acceder a información financiera sensible",
    accion_legal_o_irreversible: "Acciones legales o irreversibles",
  },
  approvalStatuses: {
    pendiente: "Pendiente",
    aprobada: "Aprobada",
    rechazada: "Rechazada",
    ejecutada: "Ejecutada",
    fallida: "Falló",
    bloqueada: "Bloqueada",
  },
  followUpStatuses: { pendiente: "Pendiente", hecho: "Hecho", cancelado: "Cancelado" },
  agents: {
    director: {
      name: "Director General AI",
      description:
        "Coordina a los demás agentes: analiza cada empresa, decide quién interviene, arma planes, compara resultados con objetivos y pide autorización para lo sensible.",
    },
    market_research: {
      name: "Market Research AI",
      description: "Investiga mercados, tendencias, demanda y comportamiento de compradores.",
    },
    competitor_intelligence: {
      name: "Competitor Intelligence AI",
      description: "Analiza competidores: precios, ofertas, posicionamiento, publicidad, fortalezas y debilidades.",
    },
    product_intelligence: {
      name: "Product Intelligence AI",
      description: "Investiga productos, demanda, rentabilidad y mejoras comerciales.",
    },
    seo_engine: {
      name: "SEO Engine AI",
      description: "Palabras clave, contenido, SEO técnico y local, Google Business Profile y productos.",
    },
    conversion_engine: {
      name: "Conversion Engine AI",
      description: "Detecta por qué los visitantes no compran y propone mejoras en diseño, textos, ofertas y proceso de compra.",
    },
    creative_engine: {
      name: "Creative Engine AI",
      description: "Propone anuncios, imágenes, videos, publicaciones y textos comerciales.",
    },
    advertising_engine: {
      name: "Advertising Engine AI",
      description: "Analiza y optimiza Google Ads y Meta Ads. Nunca aumenta gastos sin autorización.",
    },
    sales_engine: {
      name: "Sales Engine AI",
      description: "Seguimiento de interesados, organización de oportunidades, respuestas y recordatorios.",
    },
    email_engine: {
      name: "Email Engine AI",
      description: "Investiga empresas, redacta correos y propuestas personalizadas y envía solo con autorización.",
    },
    customer_recovery: {
      name: "Customer Recovery AI",
      description: "Detecta clientes que dejaron de comprar, consultas sin responder y carritos abandonados.",
    },
    financial_intelligence: {
      name: "Financial Intelligence AI",
      description: "Analiza ventas, costos, márgenes y rentabilidad, distinguiendo facturación, ganancia bruta, margen y beneficio neto.",
    },
    customer_experience: {
      name: "Customer Experience AI",
      description: "Analiza consultas, reclamos y reseñas para detectar problemas repetidos.",
    },
  },
} as const;

export type Dictionary = typeof es;
