/**
 * Reglas que convierten los hechos medidos en hallazgos. Cada hallazgo es un HECHO con su evidencia:
 * describe lo que se vio (o no se vio) en la página analizada, sin suponer causas ni resultados.
 * Importante: solo se analiza la página principal, y eso se aclara en cada texto.
 */
import type { Finding, SiteFacts } from "./types";

type Draft = Omit<Finding, "kind" | "sourceUrl"> & { sourceUrl?: string | null };

export function buildFindings(f: SiteFacts, opts: { now?: Date } = {}): Finding[] {
  const out: Draft[] = [];
  const page = f.finalUrl ?? f.requestedUrl;
  const year = (opts.now ?? new Date()).getFullYear();

  if (!f.robotsAllowed) {
    out.push({
      code: "robots_bloquea",
      category: "acceso",
      severity: "info",
      title: "El sitio pide no ser analizado por robots",
      detail: "Su archivo robots.txt no permite que robots lean esta página. Se respetó y no se analizó el contenido.",
      evidence: `${new URL(page).origin}/robots.txt`,
      recommendation: "Revisar el sitio manualmente si se quiere evaluar.",
      service: null,
    });
    return out.map(finalize(page));
  }

  if (f.error) {
    out.push({
      code: "sitio_no_responde",
      category: "acceso",
      severity: "critica",
      title: "No se pudo abrir el sitio web",
      detail: `Al intentar abrir ${f.requestedUrl} ocurrió: ${f.error.replace(/\.$/, "")}. Puede ser un problema temporal o una dirección mal cargada: conviene verificarlo a mano antes de mencionarlo.`,
      evidence: f.error,
      recommendation: "Verificar la dirección. Si el sitio está caído, es un problema urgente para la empresa.",
      service: "Sitio web",
    });
    return out.map(finalize(page));
  }

  if (f.statusCode && f.statusCode >= 400) {
    out.push({
      code: "error_http",
      category: "acceso",
      severity: "critica",
      title: `La página principal responde con error ${f.statusCode}`,
      detail: "Quien entra al sitio ve una página de error en lugar del contenido.",
      evidence: `Código HTTP ${f.statusCode}`,
      recommendation: "Revisar el servidor o la configuración del sitio.",
      service: "Sitio web",
    });
  }

  if (!f.https) {
    out.push({
      code: "sin_https",
      category: "seguridad",
      severity: "critica",
      title: "El sitio no usa conexión segura (https)",
      detail: "Los navegadores marcan estos sitios como «No seguro», lo que genera desconfianza, sobre todo en formularios.",
      evidence: `La página final es ${page}`,
      recommendation: "Instalar un certificado SSL (suele ser gratuito) y redirigir todo a https.",
      service: "Sitio web",
    });
  } else if (f.httpRedirectsToHttps === false) {
    out.push({
      code: "http_sin_redireccion",
      category: "seguridad",
      severity: "media",
      title: "La versión sin «s» (http) no redirige a la segura",
      detail: "Quien escribe la dirección sin https puede quedar en una versión no segura del sitio.",
      evidence: `http://${new URL(page).host} no redirige a https`,
      recommendation: "Configurar la redirección permanente de http a https.",
      service: "Sitio web",
    });
  }

  if (f.mixedContent > 0) {
    out.push({
      code: "contenido_mixto",
      category: "seguridad",
      severity: "media",
      title: "La página segura carga recursos inseguros",
      detail: `${f.mixedContent} recurso(s) se cargan por http dentro de una página https; algunos navegadores los bloquean.`,
      evidence: `${f.mixedContent} recurso(s) http`,
      recommendation: "Cambiar esos recursos a https.",
      service: "Sitio web",
    });
  }

  if (!f.viewport) {
    out.push({
      code: "sin_version_celular",
      category: "celular",
      severity: "alta",
      title: "La página no está preparada para celulares",
      detail: "No tiene la etiqueta «viewport», que indica a los celulares cómo mostrar la página. Lo habitual es que se vea chica o desordenada en el teléfono.",
      evidence: "Falta <meta name=\"viewport\">",
      recommendation: "Adaptar el diseño a celulares (diseño responsive).",
      service: "Sitio web / Conversión",
    });
  }

  if (!f.title) {
    out.push({
      code: "sin_titulo",
      category: "seo",
      severity: "alta",
      title: "La página principal no tiene título",
      detail: "El título es lo que Google muestra en sus resultados y en la pestaña del navegador.",
      evidence: "Falta <title>",
      recommendation: "Escribir un título con el nombre de la empresa y lo que ofrece.",
      service: "SEO",
    });
  } else if (f.title.length < 15 || f.title.length > 70) {
    out.push({
      code: "titulo_largo_o_corto",
      category: "seo",
      severity: "baja",
      title: f.title.length < 15 ? "El título de la página es muy corto" : "El título de la página es muy largo",
      detail: `Tiene ${f.title.length} caracteres; lo recomendable es entre 15 y 70 para que Google lo muestre completo y sea descriptivo.`,
      evidence: `«${f.title}»`,
      recommendation: "Ajustar el título incluyendo qué ofrece la empresa y dónde.",
      service: "SEO",
    });
  }

  if (!f.metaDescription) {
    out.push({
      code: "sin_descripcion",
      category: "seo",
      severity: "media",
      title: "Falta la descripción para Google",
      detail: "Sin la «meta description», Google arma un texto automático que puede no invitar a entrar.",
      evidence: "Falta <meta name=\"description\">",
      recommendation: "Escribir una descripción de 120-160 caracteres con una propuesta clara.",
      service: "SEO",
    });
  }

  if (f.h1.length === 0) {
    out.push({
      code: "sin_h1",
      category: "seo",
      severity: "baja",
      title: "La página no tiene un título principal (H1)",
      detail: "El encabezado principal ayuda a Google y a los visitantes a entender de qué trata la página.",
      evidence: "No hay etiquetas <h1>",
      recommendation: "Agregar un encabezado principal descriptivo.",
      service: "SEO",
    });
  } else if (f.h1.length > 1) {
    out.push({
      code: "varios_h1",
      category: "seo",
      severity: "baja",
      title: "La página tiene varios títulos principales (H1)",
      detail: `Tiene ${f.h1.length} encabezados H1; lo recomendable es uno solo.`,
      evidence: f.h1.map((h) => `«${h.slice(0, 60)}»`).join(", "),
      recommendation: "Dejar un único H1 y usar H2/H3 para el resto.",
      service: "SEO",
    });
  }

  const hasAnalytics = f.tracking.ga4.length > 0 || f.tracking.gtm.length > 0 || f.tracking.universalAnalytics;
  const hasAdsTags = f.tracking.googleAds.length > 0 || f.tracking.metaPixel || f.tracking.tiktokPixel;
  if (!hasAnalytics) {
    out.push({
      code: "sin_medicion",
      category: "medicion",
      severity: hasAdsTags ? "alta" : "media",
      title: "No se detecta medición de visitas (Google Analytics)",
      detail: hasAdsTags
        ? "Hay etiquetas de publicidad pero no de analítica: es difícil saber qué pasa con las visitas que se pagan."
        : "Sin analítica no se puede saber cuántas visitas llegan, de dónde vienen ni qué hacen.",
      evidence: "No se encontraron etiquetas G-, GTM- ni UA- en la página principal",
      recommendation: "Instalar Google Analytics 4 (gratis) y definir las conversiones importantes.",
      service: "Medición",
    });
  } else if (f.tracking.universalAnalytics && f.tracking.ga4.length === 0 && f.tracking.gtm.length === 0) {
    out.push({
      code: "analytics_obsoleto",
      category: "medicion",
      severity: "alta",
      title: "Usa una versión de Google Analytics que ya no funciona",
      detail: "Google dejó de procesar datos de Universal Analytics (UA-) en 2023: la medición actual probablemente no registra nada.",
      evidence: "Etiqueta UA- sin GA4",
      recommendation: "Migrar a Google Analytics 4.",
      service: "Medición",
    });
  }

  if (f.tracking.googleAds.length > 0 || f.tracking.metaPixel) {
    out.push({
      code: "invierte_en_publicidad",
      category: "publicidad",
      severity: "info",
      title: "Tiene instaladas etiquetas de publicidad",
      detail:
        "Se detectaron etiquetas de " +
        [f.tracking.googleAds.length ? "Google Ads" : null, f.tracking.metaPixel ? "Meta (Facebook/Instagram)" : null].filter(Boolean).join(" y ") +
        ". Es una señal de que invierte o invirtió en anuncios; no indica cuánto ni si están activos.",
      evidence: [...f.tracking.googleAds, f.tracking.metaPixel ? "fbq / fbevents.js" : null].filter(Boolean).join(", "),
      recommendation: "Revisar con la empresa la rentabilidad de sus campañas.",
      service: "Publicidad",
    });
  }

  const channels = f.contact.whatsapp.length + f.contact.phones.length + f.contact.forms + f.contact.emails.length;
  if (channels === 0) {
    out.push({
      code: "sin_contacto_visible",
      category: "contacto",
      severity: "alta",
      title: "La página principal no muestra cómo contactar a la empresa",
      detail: "No se encontraron enlaces de WhatsApp, teléfonos clicables, formularios ni emails en la página principal.",
      evidence: "0 canales de contacto detectados",
      recommendation: "Agregar un botón de WhatsApp y un teléfono visibles.",
      service: "Conversión",
    });
  } else if (f.contact.whatsapp.length === 0) {
    out.push({
      code: "sin_whatsapp",
      category: "contacto",
      severity: "media",
      title: "No hay botón de WhatsApp en la página principal",
      detail: "En Uruguay gran parte de las consultas comerciales llegan por WhatsApp; no se encontró un enlace directo.",
      evidence: "Sin enlaces wa.me / api.whatsapp.com",
      recommendation: "Agregar un botón de WhatsApp con un mensaje inicial.",
      service: "Conversión",
    });
  }

  if (f.copyrightYear && f.copyrightYear < year - 1) {
    out.push({
      code: "sitio_desactualizado",
      category: "confianza",
      severity: "baja",
      title: `El pie de página dice © ${f.copyrightYear}`,
      detail: "Puede dar la impresión de que el sitio está abandonado.",
      evidence: `© ${f.copyrightYear}`,
      recommendation: "Actualizar el año y revisar que el contenido esté vigente.",
      service: "Sitio web",
    });
  }

  if (!f.jsonLdTypes.some((t) => /LocalBusiness|Organization|Store|AutoDealer|RealEstateAgent|Product/i.test(t))) {
    out.push({
      code: "sin_datos_estructurados",
      category: "seo_local",
      severity: "baja",
      title: "No tiene datos estructurados para Google",
      detail: "Los datos estructurados (schema.org) ayudan a Google a mostrar dirección, horarios o productos en los resultados.",
      evidence: f.jsonLdTypes.length ? `Solo: ${f.jsonLdTypes.join(", ")}` : "Sin JSON-LD",
      recommendation: "Agregar datos de tipo LocalBusiness (o Product en tiendas).",
      service: "SEO local",
    });
  }

  if (f.imagesTotal >= 5 && f.imagesWithoutAlt / f.imagesTotal > 0.5) {
    out.push({
      code: "imagenes_sin_alt",
      category: "seo",
      severity: "baja",
      title: "La mayoría de las imágenes no tiene descripción",
      detail: `${f.imagesWithoutAlt} de ${f.imagesTotal} imágenes no tienen texto alternativo (alt), que usan Google y los lectores de pantalla.`,
      evidence: `${f.imagesWithoutAlt}/${f.imagesTotal} sin alt`,
      recommendation: "Describir las imágenes importantes.",
      service: "SEO",
    });
  }

  if (f.responseMs && f.responseMs > 3000) {
    out.push({
      code: "respuesta_lenta",
      category: "velocidad",
      severity: "media",
      title: "La página tardó en responder",
      detail: `En esta medición puntual tardó ${(f.responseMs / 1000).toFixed(1)} segundos en entregar la página (sin contar imágenes). Una sola medición puede variar.`,
      evidence: `${f.responseMs} ms`,
      recommendation: "Revisar el hosting y el tamaño de la página.",
      service: "Sitio web",
    });
  }

  if (f.pagespeed?.ok && f.pagespeed.performance !== null && f.pagespeed.performance < 50) {
    out.push({
      code: "pagespeed_bajo",
      category: "velocidad",
      severity: "alta",
      title: `Google califica la velocidad en celular con ${f.pagespeed.performance}/100`,
      detail: "Según la herramienta oficial PageSpeed Insights, la página es lenta en celulares; los visitantes suelen abandonar páginas lentas.",
      evidence: `PageSpeed móvil: ${f.pagespeed.performance}/100${f.pagespeed.lcpMs ? `, LCP ${(f.pagespeed.lcpMs / 1000).toFixed(1)} s` : ""}`,
      recommendation: "Optimizar imágenes, scripts y hosting.",
      service: "Sitio web",
    });
  }

  if (Object.keys(f.social).length === 0) {
    out.push({
      code: "sin_redes",
      category: "confianza",
      severity: "baja",
      title: "No enlaza a redes sociales",
      detail: "La página principal no tiene enlaces a Instagram, Facebook, LinkedIn u otras redes.",
      evidence: "0 enlaces a redes",
      recommendation: "Enlazar las redes activas de la empresa.",
      service: "Redes sociales",
    });
  }

  return out.map(finalize(page));
}

function finalize(page: string) {
  return (d: Draft): Finding => ({ ...d, kind: "hecho", sourceUrl: d.sourceUrl ?? page });
}
