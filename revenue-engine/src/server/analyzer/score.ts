/**
 * Puntuación de oportunidad (0-100). Fórmula fija y visible, sin IA:
 *  - Necesidad (hasta 50): problemas solucionables encontrados.
 *  - Capacidad de inversión (hasta 25): señales de que ya invierte en lo digital.
 *  - Contactabilidad (hasta 25): qué tan fácil es llegar a alguien.
 * Sirve para PRIORIZAR a quién contactar primero. No predice ventas ni que la empresa vaya a comprar.
 */
import type { Finding, ScoreItem, ScoreResult, Severity, SiteFacts } from "./types";

const SEVERITY_POINTS: Record<Severity, number> = { critica: 15, alta: 10, media: 6, baja: 2, info: 0 };
const MAX = { necesidad: 50, inversion: 25, contacto: 25 } as const;

export function computeScore(f: SiteFacts, findings: Finding[]): ScoreResult {
  const items: ScoreItem[] = [];

  // Necesidad. Si no se pudo analizar (robots o sitio caído), no se suman problemas que no medimos.
  for (const x of findings) {
    const p = SEVERITY_POINTS[x.severity];
    if (p > 0) items.push({ group: "necesidad", label: x.title, points: p });
  }

  // Capacidad de inversión
  if (f.tracking.googleAds.length || f.tracking.metaPixel || f.tracking.tiktokPixel) {
    items.push({ group: "inversion", label: "Tiene etiquetas de publicidad (invierte o invirtió en anuncios)", points: 10 });
  }
  if (f.ecommerceSignals) items.push({ group: "inversion", label: "Vende en línea (tienda o carrito)", points: 7 });
  if (Object.keys(f.social).length >= 2) items.push({ group: "inversion", label: "Presencia en 2 o más redes sociales", points: 4 });
  if (f.wordCount > 300) items.push({ group: "inversion", label: "Sitio con contenido desarrollado", points: 4 });

  // Contactabilidad
  if (f.contact.emails.length) items.push({ group: "contacto", label: "Publica un email", points: 10 });
  if (f.contact.whatsapp.length) items.push({ group: "contacto", label: "Publica WhatsApp", points: 8 });
  if (f.contact.phones.length) items.push({ group: "contacto", label: "Publica teléfono", points: 4 });
  if (f.contact.forms) items.push({ group: "contacto", label: "Tiene formulario de contacto", points: 3 });

  const groups = {
    necesidad: { points: 0, max: MAX.necesidad },
    inversion: { points: 0, max: MAX.inversion },
    contacto: { points: 0, max: MAX.contacto },
  };
  for (const it of items) groups[it.group].points += it.points;
  for (const g of Object.values(groups)) g.points = Math.min(g.points, g.max);

  return { score: groups.necesidad.points + groups.inversion.points + groups.contacto.points, items, groups };
}
