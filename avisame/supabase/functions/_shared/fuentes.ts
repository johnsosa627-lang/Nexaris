// Fuentes de vehículos externas. Cada fuente convierte sus datos al formato de
// la tabla `vehiculos` (source, external_id, external_url, ...). Se guardan con
// upsert sobre (source, external_id), así una nueva importación actualiza en
// vez de duplicar.
//
// Reglas: solo APIs oficiales o datos propios del vendedor. Nada de scraping
// ni de nada que viole los términos de otra plataforma.
//  - 'mercadolibre': API oficial de Mercado Libre (requiere una app registrada
//    en developers.mercadolibre.com.uy y respetar sus términos y límites).
//  - 'facebook_propio': solo el inventario propio del vendedor, exportado por
//    él mismo (por ejemplo, el catálogo de su cuenta comercial de Meta).
import { normalizar, tipoSugerido, ubicacionDe, type Combustible, type Tipo, type Transmision } from './nucleo.ts';

export type Fuente = 'mercadolibre' | 'facebook_propio';

export type VehiculoExterno = {
  source: Fuente;
  external_id: string;
  external_url: string | null;
  marca: string;
  modelo: string;
  version: string | null;
  anio: number;
  km: number;
  precio_usd: number;
  transmision: Transmision;
  combustible: Combustible;
  tipo: Tipo;
  traccion_4x4: boolean;
  descripcion: string | null;
  departamento: string;
  ciudad: string;
  lat: number;
  lng: number;
  fotos: string[];
  contacto_nombre: string;
  contacto_whatsapp: string;
};

/** Ítem de la API oficial de Mercado Libre (GET /items/{id}), solo lo que usamos. */
export type ItemMercadoLibre = {
  id: string;
  title: string;
  price: number;
  currency_id: string;
  permalink: string;
  pictures?: { secure_url?: string; url?: string }[];
  attributes?: { id: string; value_name: string | null }[];
  location?: { state?: { name?: string }; city?: { name?: string } };
  seller_address?: { state?: { name?: string }; city?: { name?: string } };
};

/**
 * Convierte un ítem de Mercado Libre. Devuelve null si faltan datos
 * esenciales o si el precio no está en dólares (no convertimos monedas).
 */
export function desdeMercadoLibre(item: ItemMercadoLibre, contacto: { nombre: string; telefono: string }): VehiculoExterno | null {
  const attr = (id: string) => item.attributes?.find((a) => a.id === id)?.value_name ?? null;
  const marca = attr('BRAND');
  const modelo = attr('MODEL');
  const anio = Number(attr('VEHICLE_YEAR'));
  const km = Number((attr('KILOMETERS') ?? '').replace(/\D/g, ''));
  if (!marca || !modelo || !anio || item.currency_id !== 'USD') return null;
  const lugarML = item.location ?? item.seller_address;
  const u = ubicacionDe(lugarML?.state?.name ?? '', lugarML?.city?.name ?? null);
  if (!u) return null;
  const trans = normalizar(attr('TRANSMISSION') ?? '');
  const comb = normalizar(attr('FUEL_TYPE') ?? '');
  const traccion = normalizar(attr('TRACTION_CONTROL') ?? attr('DRIVETRAIN') ?? '');
  return {
    source: 'mercadolibre',
    external_id: item.id,
    external_url: item.permalink,
    marca,
    modelo,
    version: attr('TRIM'),
    anio,
    km: Number.isFinite(km) ? km : 0,
    precio_usd: Math.round(item.price),
    transmision: trans.includes('autom') ? 'automatica' : 'manual',
    combustible: comb.includes('diesel') ? 'diesel' : comb.includes('hibrid') ? 'hibrido' : comb.includes('electr') ? 'electrico' : 'nafta',
    tipo: tipoSugerido(marca, modelo) ?? 'otro',
    traccion_4x4: /4x4|4wd|awd|integral/.test(traccion),
    descripcion: null,
    departamento: u.departamento,
    ciudad: u.ciudad,
    lat: u.lat,
    lng: u.lng,
    fotos: (item.pictures ?? []).map((p) => p.secure_url ?? p.url ?? '').filter(Boolean).slice(0, 10),
    contacto_nombre: contacto.nombre,
    contacto_whatsapp: contacto.telefono,
  };
}
