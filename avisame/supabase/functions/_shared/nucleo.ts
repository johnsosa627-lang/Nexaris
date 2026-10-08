// ─────────────────────────────────────────────────────────────────────────────
// Avisame · núcleo compartido
//
// Este archivo lo usan tanto la app (Expo) como las funciones del servidor
// (Supabase Edge Functions / Deno). No tiene dependencias ni usa APIs de
// plataforma: solo TypeScript puro.
//
// Contiene: lugares de Uruguay, catálogo de marcas y modelos, planes, el
// intérprete de búsquedas en lenguaje natural, las reglas de coincidencia y
// el cálculo de distancias.
// ─────────────────────────────────────────────────────────────────────────────

// ═════════════════════════════ Tipos básicos ═════════════════════════════════

export type Transmision = 'manual' | 'automatica';
export type Combustible = 'nafta' | 'diesel' | 'hibrido' | 'electrico';
export type Tipo = 'sedan' | 'hatch' | 'suv' | 'pickup' | 'utilitario' | 'otro';

export const TRANSMISIONES: { id: Transmision; nombre: string }[] = [
  { id: 'manual', nombre: 'Manual' },
  { id: 'automatica', nombre: 'Automática' },
];

export const COMBUSTIBLES: { id: Combustible; nombre: string }[] = [
  { id: 'nafta', nombre: 'Nafta' },
  { id: 'diesel', nombre: 'Diésel' },
  { id: 'hibrido', nombre: 'Híbrido' },
  { id: 'electrico', nombre: 'Eléctrico' },
];

export const TIPOS: { id: Tipo; nombre: string }[] = [
  { id: 'sedan', nombre: 'Sedán' },
  { id: 'hatch', nombre: 'Hatch' },
  { id: 'suv', nombre: 'SUV' },
  { id: 'pickup', nombre: 'Pickup' },
  { id: 'utilitario', nombre: 'Utilitario' },
  { id: 'otro', nombre: 'Otro' },
];

export function nombreTransmision(t: Transmision): string {
  return t === 'automatica' ? 'Automática' : 'Manual';
}
export function nombreCombustible(c: Combustible): string {
  return COMBUSTIBLES.find((x) => x.id === c)?.nombre ?? c;
}
export function nombreTipo(t: Tipo): string {
  return TIPOS.find((x) => x.id === t)?.nombre ?? t;
}

/** Datos mínimos de un vehículo que necesita el núcleo (mismos nombres que la base). */
export type VehiculoBase = {
  marca: string;
  modelo: string;
  version?: string | null;
  anio: number;
  km: number;
  precio_usd: number;
  transmision: Transmision;
  combustible: Combustible;
  tipo: Tipo;
  traccion_4x4: boolean;
  departamento: string;
  ciudad: string;
  lat: number;
  lng: number;
  destacado?: boolean;
  creado?: string;
};

/** Un punto de referencia: dónde está la persona o el vehículo. */
export type Ubicacion = {
  departamento: string;
  ciudad: string;
  lat: number;
  lng: number;
};

/**
 * Lo que la app entendió de la búsqueda. Hoy lo genera `interpretar()` con
 * reglas locales; mañana lo puede generar una IA devolviendo este mismo objeto.
 */
export type Criterios = {
  marca?: string;
  modelo?: string;
  anioMin?: number;
  anioMax?: number;
  kmMax?: number;
  precioMin?: number;
  precioMax?: number;
  transmision?: Transmision;
  combustible?: Combustible;
  tipo?: Tipo;
  traccion4x4?: boolean;
  /** Lugar mencionado en la búsqueda ("en Salto"). Nunca filtra: solo ordena. */
  lugar?: Ubicacion;
};

// ═════════════════════════════ Texto y números ═══════════════════════════════

/** Minúsculas, sin tildes, sin signos raros, espacios simples. */
export function normalizar(texto: string): string {
  return texto
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9$.,+\-\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/** 70000 → "70.000" (separador de miles uruguayo). */
export function formatoNumero(n: number): string {
  const entero = Math.round(Math.abs(n)).toString();
  const conPuntos = entero.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return (n < 0 ? '-' : '') + conPuntos;
}

export function formatoUSD(n: number): string {
  return 'USD ' + formatoNumero(n);
}

export function formatoPesos(n: number): string {
  return '$ ' + formatoNumero(n);
}

export function anioActual(): number {
  return new Date().getFullYear();
}

// ═════════════════════════════ Lugares de Uruguay ════════════════════════════

export type Ciudad = { nombre: string; lat: number; lng: number };
export type Departamento = { nombre: string; ciudades: Ciudad[] };

const c = (nombre: string, lat: number, lng: number): Ciudad => ({ nombre, lat, lng });

/** Los 19 departamentos con sus ciudades principales. La primera ciudad es la capital. */
export const DEPARTAMENTOS: Departamento[] = [
  { nombre: 'Artigas', ciudades: [c('Artigas', -30.4, -56.4667), c('Bella Unión', -30.2597, -57.5994), c('Tomás Gomensoro', -30.4286, -57.4361), c('Baltasar Brum', -30.73, -57.32)] },
  { nombre: 'Canelones', ciudades: [c('Canelones', -34.5228, -56.2778), c('Ciudad de la Costa', -34.8167, -55.95), c('Las Piedras', -34.7302, -56.2192), c('Pando', -34.7172, -55.9584), c('La Paz', -34.7614, -56.2247), c('Barros Blancos', -34.7542, -56.0028), c('Progreso', -34.6667, -56.2167), c('Santa Lucía', -34.4533, -56.3906), c('Atlántida', -34.7719, -55.7583), c('Parque del Plata', -34.7667, -55.7167), c('Salinas', -34.775, -55.83), c('Toledo', -34.7333, -56.1), c('Sauce', -34.65, -56.0667), c('Santa Rosa', -34.4986, -56.0386), c('San Ramón', -34.2914, -55.955), c('Tala', -34.3442, -55.7631), c('Empalme Olmos', -34.7, -55.9)] },
  { nombre: 'Cerro Largo', ciudades: [c('Melo', -32.3667, -54.1833), c('Río Branco', -32.5972, -53.3833), c('Fraile Muerto', -32.5167, -54.5333)] },
  { nombre: 'Colonia', ciudades: [c('Colonia del Sacramento', -34.4626, -57.84), c('Carmelo', -34.0, -58.2833), c('Juan Lacaze', -34.4333, -57.45), c('Nueva Helvecia', -34.3, -57.2333), c('Rosario', -34.3167, -57.35), c('Nueva Palmira', -33.8833, -58.4167), c('Tarariras', -34.2833, -57.6167), c('Colonia Valdense', -34.34, -57.27)] },
  { nombre: 'Durazno', ciudades: [c('Durazno', -33.3833, -56.5167), c('Sarandí del Yí', -33.35, -55.6333), c('Carmen', -33.2333, -56.0167)] },
  { nombre: 'Flores', ciudades: [c('Trinidad', -33.5167, -56.9), c('Ismael Cortinas', -33.96, -57.1)] },
  { nombre: 'Florida', ciudades: [c('Florida', -34.0956, -56.2142), c('Sarandí Grande', -33.7333, -56.3333), c('Casupá', -34.1, -55.65), c('Fray Marcos', -34.18, -55.74)] },
  { nombre: 'Lavalleja', ciudades: [c('Minas', -34.3667, -55.2333), c('José Pedro Varela', -33.45, -54.5333), c('Solís de Mataojo', -34.6, -55.47)] },
  { nombre: 'Maldonado', ciudades: [c('Maldonado', -34.9, -54.95), c('Punta del Este', -34.96, -54.95), c('San Carlos', -34.7917, -54.9181), c('Piriápolis', -34.8667, -55.2833), c('Pan de Azúcar', -34.7833, -55.2333), c('Aiguá', -34.2, -54.75)] },
  { nombre: 'Montevideo', ciudades: [c('Montevideo', -34.9011, -56.1645)] },
  { nombre: 'Paysandú', ciudades: [c('Paysandú', -32.3214, -58.0756), c('Guichón', -32.35, -57.2), c('Quebracho', -31.95, -57.9)] },
  { nombre: 'Río Negro', ciudades: [c('Fray Bentos', -33.1325, -58.2956), c('Young', -32.7, -57.6333), c('Nuevo Berlín', -32.98, -58.06)] },
  { nombre: 'Rivera', ciudades: [c('Rivera', -30.9053, -55.5508), c('Tranqueras', -31.2, -55.75), c('Vichadero', -31.78, -54.69)] },
  { nombre: 'Rocha', ciudades: [c('Rocha', -34.4833, -54.3333), c('Chuy', -33.6833, -53.45), c('Castillos', -34.2, -53.8333), c('Lascano', -33.6667, -54.2), c('La Paloma', -34.6667, -54.1667)] },
  { nombre: 'Salto', ciudades: [c('Salto', -31.3833, -57.9667), c('Constitución', -31.08, -57.84), c('Belén', -30.79, -57.78)] },
  { nombre: 'San José', ciudades: [c('San José de Mayo', -34.3375, -56.7136), c('Ciudad del Plata', -34.7667, -56.3833), c('Libertad', -34.6333, -56.6167), c('Ecilda Paullier', -34.36, -57.05), c('Rodríguez', -34.38, -56.54)] },
  { nombre: 'Soriano', ciudades: [c('Mercedes', -33.2524, -58.0305), c('Dolores', -33.5333, -58.2167), c('Cardona', -33.8667, -57.3833)] },
  { nombre: 'Tacuarembó', ciudades: [c('Tacuarembó', -31.7333, -55.9833), c('Paso de los Toros', -32.8167, -56.5167), c('San Gregorio de Polanco', -32.6167, -55.8333)] },
  { nombre: 'Treinta y Tres', ciudades: [c('Treinta y Tres', -33.2333, -54.3833), c('Vergara', -32.9333, -53.95), c('Santa Clara de Olimar', -32.92, -54.94)] },
];

export const UBICACION_POR_DEFECTO: Ubicacion = ubicacionDe('Montevideo', 'Montevideo')!;

export function buscarDepartamento(nombre: string): Departamento | undefined {
  const n = normalizar(nombre);
  return DEPARTAMENTOS.find((d) => normalizar(d.nombre) === n);
}

/** Ubicación de una ciudad. Si falta la ciudad o no existe, usa la capital del departamento. */
export function ubicacionDe(departamento: string, ciudad?: string | null): Ubicacion | undefined {
  const dep = buscarDepartamento(departamento);
  if (!dep) return undefined;
  const n = ciudad ? normalizar(ciudad) : '';
  const ciu = dep.ciudades.find((x) => normalizar(x.nombre) === n) ?? dep.ciudades[0];
  return { departamento: dep.nombre, ciudad: ciu.nombre, lat: ciu.lat, lng: ciu.lng };
}

/** La ciudad de la lista más cercana a unas coordenadas (para la ubicación del celular). */
export function ciudadMasCercana(lat: number, lng: number): Ubicacion {
  let mejor: Ubicacion = UBICACION_POR_DEFECTO;
  let mejorDist = Infinity;
  for (const dep of DEPARTAMENTOS) {
    for (const ciu of dep.ciudades) {
      const d = distanciaKm(lat, lng, ciu.lat, ciu.lng);
      if (d < mejorDist) {
        mejorDist = d;
        mejor = { departamento: dep.nombre, ciudad: ciu.nombre, lat: ciu.lat, lng: ciu.lng };
      }
    }
  }
  return mejor;
}

/** "Atlántida, Canelones" o "Montevideo" cuando ciudad y departamento coinciden. */
export function nombreLugar(departamento: string, ciudad: string): string {
  return normalizar(ciudad) === normalizar(departamento) ? ciudad : `${ciudad}, ${departamento}`;
}

// ═════════════════════════════ Distancias ════════════════════════════════════

/** Distancia en línea recta (fórmula del semiverseno), en kilómetros. */
export function distanciaKm(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const R = 6371;
  const rad = Math.PI / 180;
  const dLat = (lat2 - lat1) * rad;
  const dLng = (lng2 - lng1) * rad;
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(a)));
}

/** A partir de esta distancia se avisa que el vehículo está lejos. */
export const KM_LEJOS = 100;

export function textoDistancia(km: number): string {
  if (km < 1) return 'a menos de 1 km';
  return `a ${formatoNumero(km)} km`;
}

/** "⚠️ Está lejos: a 429 km de Salto", o null si está a 100 km o menos. */
export function avisoLejos(km: number, desde: string): string | null {
  if (km <= KM_LEJOS) return null;
  return `⚠️ Está lejos: ${textoDistancia(km)} de ${desde}`;
}

// ═════════════════════════════ Catálogo ══════════════════════════════════════

export type ModeloCatalogo = { nombre: string; tipo: Tipo; alias: string[]; requiereMarca: boolean };
export type MarcaCatalogo = { marca: string; alias: string[]; modelos: ModeloCatalogo[] };

// Modelos que también son palabras comunes o números: solo se reconocen si
// la marca aparece en la búsqueda ("Fiat Uno", "Kia Rio", "Peugeot 208").
const MODELOS_AMBIGUOS = new Set(['uno', 'up', 'rio', 'alto', 'one', 'fiesta', 'toro', 'city', 'spin', 'note', 'march', 'ka', 'kona', 'seal', 'song', 'hr', 'view', 'joy', 'hunter', 'master']);

/** Formato compacto: "Nombre/tipo/alias1;alias2, Nombre/tipo". */
function marca(nombre: string, alias: string[], modelos: string): MarcaCatalogo {
  return {
    marca: nombre,
    alias: [normalizar(nombre), ...alias],
    modelos: modelos.split(',').map((m) => {
      const [nom, tipo, al] = m.trim().split('/');
      const normal = normalizar(nom);
      const alias = [normal, normal.replace(/-/g, ' '), normal.replace(/[-\s]/g, ''), ...(al ? al.split(';') : [])];
      return {
        nombre: nom,
        tipo: tipo as Tipo,
        alias: [...new Set(alias)],
        requiereMarca: /^\d+$/.test(normal) || MODELOS_AMBIGUOS.has(normal),
      };
    }),
  };
}

export const CATALOGO: MarcaCatalogo[] = [
  marca('Toyota', [], 'Corolla/sedan, Corolla Cross/suv, Yaris/hatch, Etios/hatch, Hilux/pickup, SW4/suv/sw 4, RAV4/suv/rav 4, Hiace/utilitario, Land Cruiser/suv, Prius/hatch'),
  marca('Volkswagen', ['vw', 'volks', 'volkswagen', 'wolkswagen'], 'Gol/hatch, Polo/hatch, Virtus/sedan, Vento/sedan, Voyage/sedan, Up/hatch, Fox/hatch, Suran/hatch, T-Cross/suv, Nivus/suv, Taos/suv, Tiguan/suv, Amarok/pickup, Saveiro/pickup, Golf/hatch'),
  marca('Chevrolet', ['chevy', 'chevrolet'], 'Onix/hatch, Onix Plus/sedan, Prisma/sedan, Cruze/sedan, Tracker/suv, S10/pickup/s 10, Montana/pickup, Spin/otro, Equinox/suv, Celta/hatch, Corsa/hatch, Aveo/sedan, Sail/sedan, Joy/hatch, N300/utilitario'),
  marca('Fiat', [], 'Uno/hatch, Mobi/hatch, Argo/hatch, Cronos/sedan, Palio/hatch, Siena/sedan, Strada/pickup, Toro/pickup, Pulse/suv, Fastback/suv, Fiorino/utilitario, Ducato/utilitario, 500/hatch'),
  marca('Renault', [], 'Kwid/hatch, Sandero/hatch, Stepway/hatch/sandero stepway, Logan/sedan, Clio/hatch, Duster/suv, Captur/suv, Oroch/pickup/duster oroch, Kangoo/utilitario, Master/utilitario, Symbol/sedan'),
  marca('Peugeot', [], '208/hatch, 2008/suv, 3008/suv, 308/hatch, 301/sedan, 408/sedan, 207/hatch, Partner/utilitario, Expert/utilitario, Boxer/utilitario'),
  marca('Citroën', ['citroen'], 'C3/hatch, C3 Aircross/suv, C4 Cactus/suv/cactus, C4/hatch, C-Elysée/sedan/c elysee;celysee, Berlingo/utilitario, Jumpy/utilitario'),
  marca('Ford', [], 'Ka/hatch, Fiesta/hatch, Focus/hatch, EcoSport/suv/eco sport, Territory/suv, Kuga/suv, Bronco Sport/suv/bronco, Ranger/pickup, Maverick/pickup, Transit/utilitario'),
  marca('Hyundai', ['hiundai', 'hyunday'], 'HB20/hatch/hb 20, Grand i10/hatch/i10;grand i 10, Accent/sedan, Elantra/sedan, Creta/suv, Venue/suv, Kona/suv, Tucson/suv, Santa Fe/suv, H1/utilitario/h 1, HR/utilitario'),
  marca('Kia', [], 'Picanto/hatch, Rio/hatch, Soluto/sedan, Cerato/sedan, Sonet/suv, Seltos/suv, Sportage/suv, Sorento/suv, K2700/utilitario/k 2700'),
  marca('Nissan', [], 'March/hatch, Note/hatch, Versa/sedan, Sentra/sedan, Tiida/hatch, Kicks/suv, X-Trail/suv/xtrail, Frontier/pickup'),
  marca('Suzuki', [], 'Alto/hatch, Celerio/hatch, S-Presso/hatch/spresso, Swift/hatch, Baleno/hatch, Dzire/sedan, Ertiga/otro, Vitara/suv, Grand Vitara/suv, Jimny/suv'),
  marca('Honda', [], 'Fit/hatch, City/sedan, Civic/sedan, WR-V/suv, HR-V/suv, CR-V/suv'),
  marca('Mitsubishi', [], 'L200/pickup/l 200, Outlander/suv, ASX/suv, Montero/suv, Lancer/sedan'),
  marca('Chery', [], 'QQ/hatch, Arrizo 5/sedan/arrizo, Tiggo 2/suv, Tiggo 3/suv, Tiggo 4/suv, Tiggo 7/suv, Tiggo 8/suv'),
  marca('Geely', [], 'Emgrand/sedan, GX3/suv, Coolray/suv'),
  marca('BYD', [], 'Dolphin Mini/hatch, Dolphin/hatch, Seal/sedan, Yuan Plus/suv/atto 3, Song Plus/suv, Song/suv, Shark/pickup'),
  marca('JAC', [], 'S2/suv, S3/suv, JS4/suv, T6/pickup, T8/pickup, E-JS1/hatch'),
  marca('DFSK', [], '580/suv, Glory 500/suv/glory, C31/utilitario, K01/utilitario'),
  marca('Haval', ['great wall', 'gwm'], 'H6/suv, Jolion/suv, Wingle/pickup, Poer/pickup'),
  marca('MG', [], 'MG3/hatch/mg 3, MG5/sedan/mg 5, ZS/suv, HS/suv'),
  marca('Jeep', [], 'Renegade/suv, Compass/suv, Commander/suv, Wrangler/suv, Gladiator/pickup'),
  marca('RAM', ['dodge ram'], '1500/pickup, 700/pickup'),
  marca('Mercedes-Benz', ['mercedes', 'mercedes benz', 'mb'], 'Clase A/hatch, Clase C/sedan, GLA/suv, GLC/suv, Sprinter/utilitario, Vito/utilitario'),
  marca('BMW', [], 'Serie 1/hatch/serie1, Serie 3/sedan/serie3, X1/suv, X3/suv'),
  marca('Audi', [], 'A1/hatch, A3/sedan, A4/sedan, Q2/suv, Q3/suv, Q5/suv'),
  marca('Changan', [], 'CS15/suv/cs 15, CS35/suv/cs 35, Hunter/pickup'),
  marca('Foton', [], 'Tunland/pickup, View/utilitario, Gratour/utilitario'),
];

export function modelosDe(nombreMarca: string): ModeloCatalogo[] {
  const n = normalizar(nombreMarca);
  return CATALOGO.find((m) => normalizar(m.marca) === n)?.modelos ?? [];
}

/** Tipo de carrocería sugerido para un modelo del catálogo. */
export function tipoSugerido(nombreMarca: string, nombreModelo: string): Tipo | undefined {
  const n = normalizar(nombreModelo);
  return modelosDe(nombreMarca).find((m) => normalizar(m.nombre) === n)?.tipo;
}

// ═════════════════════════════ Planes ════════════════════════════════════════
// Único lugar donde se definen los planes y sus precios (pesos uruguayos, por mes).
// La app los muestra y el servidor los usa para crear la suscripción y verificar
// el monto cobrado.

export type PlanId = 'gratis' | 'pro' | 'destacado';

export type Plan = {
  id: PlanId;
  nombre: string;
  precioUYU: number;
  beneficios: string[];
  verContactos: boolean;
  avisos: boolean;
  destacado: boolean;
};

export const PLANES: Record<PlanId, Plan> = {
  gratis: {
    id: 'gratis',
    nombre: 'Gratis',
    precioUYU: 0,
    beneficios: ['Publicá tu inventario', 'Mirá cuántas personas buscan lo que tenés'],
    verContactos: false,
    avisos: false,
    destacado: false,
  },
  pro: {
    id: 'pro',
    nombre: 'Pro',
    precioUYU: 1590,
    beneficios: ['Todo lo del plan Gratis', 'Contacto de los clientes que lo autorizaron', 'Aviso al celular cuando aparece un cliente nuevo'],
    verContactos: true,
    avisos: true,
    destacado: false,
  },
  destacado: {
    id: 'destacado',
    nombre: 'Destacado',
    precioUYU: 3190,
    beneficios: ['Todo lo del plan Pro', 'Tus vehículos primeros en las búsquedas', 'Insignia “★ Destacado”'],
    verContactos: true,
    avisos: true,
    destacado: true,
  },
};

export const PLANES_PAGOS: PlanId[] = ['pro', 'destacado'];

export function esPlanPago(id: string): id is 'pro' | 'destacado' {
  return id === 'pro' || id === 'destacado';
}

/** El plan que corresponde hoy: si el período pagado venció, vuelve a Gratis. */
export function planVigente(plan: string | null | undefined, vence: string | null | undefined, ahora = new Date()): PlanId {
  if (!plan || !esPlanPago(plan)) return 'gratis';
  if (!vence || new Date(vence).getTime() <= ahora.getTime()) return 'gratis';
  return plan;
}

// ═════════════════════════════ Intérprete ════════════════════════════════════

const AÑO_MIN = 1950;
// "$" solo no se toma como dólares: en Uruguay es el signo del peso.
const MONEDA = '(?:usd|u\\$s|us\\$|u\\$d|u\\$|dolares|dolar|dls|verdes)';
const NUM = '(\\d+)';

type Texto = { t: string };

/** Busca un patrón, devuelve sus grupos y lo borra del texto para no volver a usarlo. */
function tomar(txt: Texto, patron: RegExp): RegExpExecArray | null {
  const m = patron.exec(txt.t);
  if (!m) return null;
  txt.t = (txt.t.slice(0, m.index) + ' ' + txt.t.slice(m.index + m[0].length)).replace(/\s+/g, ' ');
  return m;
}

function esAnio(n: number): boolean {
  return n >= AÑO_MIN && n <= anioActual() + 1;
}

function escaparRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

type EntradaLugar = { clave: string; ubicacion: Ubicacion; ambigua: boolean };

// Nombres de lugar que también son palabras o marcas: solo cuentan con "en", "cerca de", etc.
const LUGARES_AMBIGUOS = new Set(['mercedes', 'carmen', 'libertad', 'progreso', 'rosario', 'dolores', 'young', 'belen', 'tala', 'sauce', 'salinas', 'toledo', 'florida', 'artigas', 'rivera', 'colonia', 'minas', 'la paz', 'constitucion', 'cardona', 'santa rosa']);

let _lugares: EntradaLugar[] | null = null;
function indiceLugares(): EntradaLugar[] {
  if (_lugares) return _lugares;
  const lista: EntradaLugar[] = [];
  for (const dep of DEPARTAMENTOS) {
    for (const ciu of dep.ciudades) {
      const u = { departamento: dep.nombre, ciudad: ciu.nombre, lat: ciu.lat, lng: ciu.lng };
      const clave = normalizar(ciu.nombre);
      lista.push({ clave, ubicacion: u, ambigua: LUGARES_AMBIGUOS.has(clave) });
      if (clave === 'san jose de mayo') lista.push({ clave: 'san jose', ubicacion: u, ambigua: false });
      if (clave === 'colonia del sacramento') lista.push({ clave: 'colonia', ubicacion: u, ambigua: true });
      if (clave === 'punta del este') lista.push({ clave: 'punta', ubicacion: u, ambigua: true });
    }
    const capital = dep.ciudades[0];
    const claveDep = normalizar(dep.nombre);
    if (!lista.some((l) => l.clave === claveDep)) {
      lista.push({
        clave: claveDep,
        ubicacion: { departamento: dep.nombre, ciudad: capital.nombre, lat: capital.lat, lng: capital.lng },
        ambigua: LUGARES_AMBIGUOS.has(claveDep),
      });
    }
  }
  lista.push({ clave: 'mvd', ubicacion: UBICACION_POR_DEFECTO, ambigua: false });
  lista.sort((a, b) => b.clave.length - a.clave.length);
  _lugares = lista;
  return lista;
}

function extraerLugar(txt: Texto, soloConPreposicion: boolean): Ubicacion | undefined {
  for (const l of indiceLugares()) {
    const nombre = escaparRegex(l.clave);
    const conPrep = new RegExp(`(?:^|\\s)(?:en|cerca de|cerca|por|zona|zona de|de|desde)\\s+(?:la ciudad de\\s+|el departamento de\\s+)?${nombre}(?=\\s|$)`);
    if (tomar(txt, conPrep)) return l.ubicacion;
    if (!soloConPreposicion && !l.ambigua && tomar(txt, new RegExp(`(?:^|\\s)${nombre}(?=\\s|$)`))) return l.ubicacion;
  }
  return undefined;
}

type EntradaModelo = { marca: MarcaCatalogo; modelo: ModeloCatalogo; alias: string };

let _modelos: EntradaModelo[] | null = null;
function indiceModelos(): EntradaModelo[] {
  if (_modelos) return _modelos;
  const lista: EntradaModelo[] = [];
  for (const m of CATALOGO) for (const mo of m.modelos) for (const alias of mo.alias) lista.push({ marca: m, modelo: mo, alias });
  lista.sort((a, b) => b.alias.length - a.alias.length);
  _modelos = lista;
  return lista;
}

function extraerVehiculo(txt: Texto): { marca?: string; modelo?: string } {
  let marcaEncontrada: MarcaCatalogo | undefined;
  const alias = CATALOGO.flatMap((m) => m.alias.map((a) => ({ m, a }))).sort((x, y) => y.a.length - x.a.length);
  for (const { m, a } of alias) {
    if (tomar(txt, new RegExp(`(?:^|\\s)${escaparRegex(a)}(?=\\s|$)`))) {
      marcaEncontrada = m;
      break;
    }
  }
  for (const e of indiceModelos()) {
    if (marcaEncontrada && e.marca !== marcaEncontrada) continue;
    if (!marcaEncontrada && e.modelo.requiereMarca) continue;
    if (tomar(txt, new RegExp(`(?:^|\\s)${escaparRegex(e.alias)}(?=\\s|$)`))) {
      return { marca: e.marca.marca, modelo: e.modelo.nombre };
    }
  }
  return { marca: marcaEncontrada?.marca };
}

/**
 * Convierte lo que escribió la persona en criterios de búsqueda.
 * Ej.: "Busco una Hyundai Creta 2022 o más nueva, menos de 70.000 km y hasta 18.000 dólares"
 */
export function interpretar(texto: string): Criterios {
  const r: Criterios = {};
  let t = ' ' + normalizar(texto) + ' ';
  // Números: "70.000" → 70000, "18 mil" / "18k" → 18000.
  t = t.replace(/(\d{1,3})(?:[.,](\d{3}))+(?!\d)/g, (m) => m.replace(/[.,]/g, ''));
  t = t.replace(/(\d+)\s*(?:mil|k|lucas)(?=\s|$|[^a-z])/g, (_, n) => String(Number(n) * 1000));
  t = t.replace(/[.,]/g, ' ').replace(/\s+/g, ' ');
  // Monedas pegadas al número: "u$s18000" → "u$s 18000".
  t = t.replace(/(u\$s|us\$|u\$d|u\$|usd)(\d)/g, '$1 $2');
  const txt: Texto = { t };

  // 1) Lugar con preposición ("en Mercedes" es un lugar, no la marca).
  const lugar = extraerLugar(txt, true);
  if (lugar) r.lugar = lugar;

  // 2) Atributos con palabras clave.
  if (tomar(txt, /\s(?:4\s?x\s?4|4wd|awd|doble traccion|traccion integral|traccion 4x4)(?=\s|$)/)) r.traccion4x4 = true;
  if (tomar(txt, /\s(?:caja\s+)?(?:automatic[oa]s?|automat|aut|cvt|at)(?=\s|$)/)) r.transmision = 'automatica';
  else if (tomar(txt, /\s(?:caja\s+)?(?:manual(?:es)?|mecanic[oa]s?)(?=\s|$)/)) r.transmision = 'manual';
  if (tomar(txt, /\s(?:a\s+)?(?:diesel|gasoil|gas oil|turbodiesel)(?=\s|$)/)) r.combustible = 'diesel';
  else if (tomar(txt, /\s(?:hibrid[oa]s?)(?=\s|$)/)) r.combustible = 'hibrido';
  else if (tomar(txt, /\s(?:electric[oa]s?)(?=\s|$)/)) r.combustible = 'electrico';
  else if (tomar(txt, /\s(?:a\s+)?(?:nafta|naftero|naftera|gasolina)(?=\s|$)/)) r.combustible = 'nafta';
  if (tomar(txt, /\s(?:suvs?|todoterreno|todo terreno|crossover)(?=\s|$)/)) r.tipo = 'suv';
  else if (tomar(txt, /\s(?:pick\s?-?\s?ups?|pickups?|chatas?)(?=\s|$)/)) r.tipo = 'pickup';
  else if (tomar(txt, /\s(?:sedan(?:es)?)(?=\s|$)/)) r.tipo = 'sedan';
  else if (tomar(txt, /\s(?:hatch(?:back)?s?)(?=\s|$)/)) r.tipo = 'hatch';
  else if (tomar(txt, /\s(?:utilitari[oa]s?|furgon(?:es)?|furgoneta|van)(?=\s|$)/)) r.tipo = 'utilitario';

  // 3) Kilómetros.
  if (tomar(txt, /\s(?:0|cero)\s*(?:km|kms|kilometros?)(?=\s|$)/)) r.kmMax = 0;
  else {
    const km =
      tomar(txt, new RegExp(`\\s(?:con\\s+)?(?:menos de|hasta|maximo|max|no mas de|como mucho|<)\\s*${NUM}\\s*(?:km|kms|kilometros?)(?=\\s|$)`)) ??
      tomar(txt, new RegExp(`\\s${NUM}\\s*(?:km|kms|kilometros?)(?:\\s+(?:o menos|maximo|como maximo))?(?=\\s|$)`));
    if (km) r.kmMax = Number(km[1]);
  }

  // 4) Precio (en dólares).
  const entrePrecio = tomar(txt, new RegExp(`\\sentre\\s+${MONEDA}?\\s*${NUM}\\s+y\\s+${MONEDA}?\\s*${NUM}\\s*${MONEDA}?(?=\\s|$)`));
  if (entrePrecio && !(esAnio(Number(entrePrecio[1])) && esAnio(Number(entrePrecio[2])) && !/usd|\$|dolar/.test(entrePrecio[0]))) {
    r.precioMin = Math.min(Number(entrePrecio[1]), Number(entrePrecio[2]));
    r.precioMax = Math.max(Number(entrePrecio[1]), Number(entrePrecio[2]));
  } else if (entrePrecio) {
    // Era un rango de años: "entre 2015 y 2019".
    r.anioMin = Math.min(Number(entrePrecio[1]), Number(entrePrecio[2]));
    r.anioMax = Math.max(Number(entrePrecio[1]), Number(entrePrecio[2]));
  }
  if (r.precioMax === undefined) {
    const max =
      tomar(txt, new RegExp(`\\s(?:hasta|menos de|maximo|max|no mas de|tope|tope de|presupuesto|presupuesto de|tengo|por)\\s+(?:unos\\s+)?${MONEDA}\\s*${NUM}(?:\\s+${MONEDA})?(?=\\s|$)`)) ??
      tomar(txt, new RegExp(`\\s(?:hasta|menos de|maximo|max|no mas de|tope|tope de|presupuesto|presupuesto de|tengo|por)\\s+(?:unos\\s+)?${NUM}\\s*${MONEDA}(?=\\s|$)`)) ??
      tomar(txt, new RegExp(`\\s${MONEDA}\\s*${NUM}(?:\\s+${MONEDA})?(?=\\s|$)`)) ??
      tomar(txt, new RegExp(`\\s${NUM}\\s*${MONEDA}(?=\\s|$)`));
    if (max) r.precioMax = Number(max[1]);
  }
  if (r.precioMin === undefined) {
    const min =
      tomar(txt, new RegExp(`\\s(?:desde|mas de|minimo|arriba de)\\s+${MONEDA}\\s*${NUM}(?:\\s+${MONEDA})?(?=\\s|$)`)) ??
      tomar(txt, new RegExp(`\\s(?:desde|mas de|minimo|arriba de)\\s+${NUM}\\s*${MONEDA}(?=\\s|$)`));
    if (min) r.precioMin = Number(min[1]);
  }

  // 5) Años.
  const rango =
    tomar(txt, /\s(?:entre(?:\s+el)?|del|de)\s+(\d{4})\s+(?:y|al|a|hasta)(?:\s+el)?\s+(\d{4})(?=\s|$)/) ?? tomar(txt, /\s(\d{4})\s*(?:-|a|al)\s*(\d{4})(?=\s|$)/);
  if (rango && esAnio(Number(rango[1])) && esAnio(Number(rango[2]))) {
    r.anioMin = Math.min(Number(rango[1]), Number(rango[2]));
    r.anioMax = Math.max(Number(rango[1]), Number(rango[2]));
  }
  const desde =
    tomar(txt, /\s(?:modelo\s+|ano\s+)?(\d{4})\s*(?:\+|(?:o|y|en|para)\s+(?:mas nuev[oa]s?|mas reciente|adelante|arriba|superior|posterior))(?=\s|$)/) ??
    tomar(txt, /\s(?:desde(?:\s+el)?|del|a partir del?|posterior al?|mas nuevo que|mas nueva que|de)\s+(?:ano\s+|modelo\s+)?(\d{4})(?:\s+en adelante|\s+para arriba)?(?=\s|$)/);
  if (desde && esAnio(Number(desde[1]))) r.anioMin = Number(desde[1]);
  const hasta =
    tomar(txt, /\s(?:modelo\s+|ano\s+)?(\d{4})\s+(?:o|y)\s+(?:mas viej[oa]s?|anterior(?:es)?|antes)(?=\s|$)/) ??
    tomar(txt, /\s(?:hasta(?:\s+el)?|antes del?|anterior al?)\s+(?:ano\s+|modelo\s+)?(\d{4})(?=\s|$)/);
  if (hasta && esAnio(Number(hasta[1]))) r.anioMax = Number(hasta[1]);

  // 6) Lugar sin preposición ("Hilux Salto") y luego marca y modelo.
  //    Primero el vehículo, así "Mercedes" sin "en" se toma como marca.
  const veh = extraerVehiculo(txt);
  if (veh.marca) r.marca = veh.marca;
  if (veh.modelo) r.modelo = veh.modelo;
  if (!r.lugar) {
    const l = extraerLugar(txt, false);
    if (l) r.lugar = l;
  }

  // 7) Un año suelto ("Corolla 2020") es ese año exacto.
  if (r.anioMin === undefined && r.anioMax === undefined) {
    const suelto = tomar(txt, /\s(?:modelo\s+|ano\s+|del\s+)?(\d{4})(?=\s|$)/);
    if (suelto && esAnio(Number(suelto[1]))) {
      r.anioMin = Number(suelto[1]);
      r.anioMax = Number(suelto[1]);
    }
  }

  // 8) Un número suelto con "hasta"/"menos de" sin unidad: si es grande, es plata.
  if (r.precioMax === undefined) {
    const n = tomar(txt, new RegExp(`\\s(?:hasta|menos de|maximo|max|no mas de|tope|presupuesto)\\s+${NUM}(?=\\s|$)`));
    if (n && Number(n[1]) >= 1000) r.precioMax = Number(n[1]);
  }

  // El tipo sale del modelo si la persona no lo dijo, pero no se agrega como filtro:
  // "Hilux" ya implica pickup.
  return r;
}

// ═════════════════════════════ Etiquetas ═════════════════════════════════════

export type ClaveCriterio = 'vehiculo' | 'anios' | 'km' | 'precio' | 'transmision' | 'combustible' | 'tipo' | 'traccion' | 'lugar';
export type Etiqueta = { clave: ClaveCriterio; texto: string };

function textoAnios(c: Criterios): string | null {
  if (c.anioMin !== undefined && c.anioMax !== undefined) {
    return c.anioMin === c.anioMax ? `Año ${c.anioMin}` : `${c.anioMin} a ${c.anioMax}`;
  }
  if (c.anioMin !== undefined) return `${c.anioMin} o más nuevo`;
  if (c.anioMax !== undefined) return `Hasta ${c.anioMax}`;
  return null;
}

function textoPrecio(c: Criterios): string | null {
  if (c.precioMin !== undefined && c.precioMax !== undefined) return `${formatoUSD(c.precioMin)} a ${formatoNumero(c.precioMax)}`;
  if (c.precioMax !== undefined) return `Hasta ${formatoUSD(c.precioMax)}`;
  if (c.precioMin !== undefined) return `Desde ${formatoUSD(c.precioMin)}`;
  return null;
}

/** Lo que la app entendió, como etiquetas para mostrar (y quitar). */
export function etiquetas(c: Criterios): Etiqueta[] {
  const e: Etiqueta[] = [];
  if (c.marca) e.push({ clave: 'vehiculo', texto: c.modelo ? `${c.marca} ${c.modelo}` : c.marca });
  const anios = textoAnios(c);
  if (anios) e.push({ clave: 'anios', texto: anios });
  if (c.kmMax !== undefined) e.push({ clave: 'km', texto: c.kmMax === 0 ? '0 km' : `Hasta ${formatoNumero(c.kmMax)} km` });
  const precio = textoPrecio(c);
  if (precio) e.push({ clave: 'precio', texto: precio });
  if (c.transmision) e.push({ clave: 'transmision', texto: nombreTransmision(c.transmision) });
  if (c.combustible) e.push({ clave: 'combustible', texto: nombreCombustible(c.combustible) });
  if (c.tipo) e.push({ clave: 'tipo', texto: nombreTipo(c.tipo) });
  if (c.traccion4x4) e.push({ clave: 'traccion', texto: '4x4' });
  if (c.lugar) e.push({ clave: 'lugar', texto: `📍 ${c.lugar.ciudad}` });
  return e;
}

export function quitarCriterio(c: Criterios, clave: ClaveCriterio): Criterios {
  const r: Criterios = { ...c };
  switch (clave) {
    case 'vehiculo': delete r.marca; delete r.modelo; break;
    case 'anios': delete r.anioMin; delete r.anioMax; break;
    case 'km': delete r.kmMax; break;
    case 'precio': delete r.precioMin; delete r.precioMax; break;
    case 'transmision': delete r.transmision; break;
    case 'combustible': delete r.combustible; break;
    case 'tipo': delete r.tipo; break;
    case 'traccion': delete r.traccion4x4; break;
    case 'lugar': delete r.lugar; break;
  }
  return r;
}

export function criteriosVacios(c: Criterios): boolean {
  return etiquetas(c).length === 0;
}

/** Frase que vuelve a escribirse en la barra después de quitar una etiqueta. */
export function textoDesdeCriterios(c: Criterios): string {
  const partes: string[] = [];
  const cabeza: string[] = [];
  if (c.tipo) cabeza.push(nombreTipo(c.tipo).toLowerCase() === 'suv' ? 'SUV' : nombreTipo(c.tipo).toLowerCase());
  if (c.marca) cabeza.push(c.modelo ? `${c.marca} ${c.modelo}` : c.marca);
  if (c.anioMin !== undefined && c.anioMax !== undefined) cabeza.push(c.anioMin === c.anioMax ? `${c.anioMin}` : `${c.anioMin} a ${c.anioMax}`);
  else if (c.anioMin !== undefined) cabeza.push(`${c.anioMin} o más nuevo`);
  else if (c.anioMax !== undefined) cabeza.push(`hasta ${c.anioMax}`);
  if (cabeza.length) partes.push(cabeza.join(' '));
  if (c.kmMax !== undefined) partes.push(c.kmMax === 0 ? '0 km' : `hasta ${formatoNumero(c.kmMax)} km`);
  if (c.precioMin !== undefined && c.precioMax !== undefined) partes.push(`entre USD ${formatoNumero(c.precioMin)} y USD ${formatoNumero(c.precioMax)}`);
  else if (c.precioMax !== undefined) partes.push(`hasta USD ${formatoNumero(c.precioMax)}`);
  else if (c.precioMin !== undefined) partes.push(`desde USD ${formatoNumero(c.precioMin)}`);
  if (c.transmision) partes.push(nombreTransmision(c.transmision).toLowerCase());
  if (c.combustible) partes.push(nombreCombustible(c.combustible).toLowerCase());
  if (c.traccion4x4) partes.push('4x4');
  if (c.lugar) partes.push(`en ${c.lugar.ciudad}`);
  const frase = partes.join(', ');
  return frase ? frase.charAt(0).toUpperCase() + frase.slice(1) : '';
}

/** Resumen corto para listas: "Hyundai Creta · 2022 o más nuevo · Hasta USD 18.000". */
export function resumenCriterios(c: Criterios): string {
  const e = etiquetas(c).filter((x) => x.clave !== 'lugar').map((x) => x.texto);
  return e.length ? e.join(' · ') : 'Cualquier vehículo';
}

// ═════════════════════════════ Coincidencias ═════════════════════════════════

/** Tolerancias para mostrar algo como "Casi". */
export const TOLERANCIA = {
  precio: 0.15, // hasta 15 % arriba del presupuesto
  km: 0.25, // hasta 25 % más de kilómetros
  anios: 1, // un año de diferencia
  maxMotivos: 2, // a lo sumo dos diferencias
};

export type Evaluacion = { estado: 'coincide' | 'casi' | 'no'; motivos: string[] };

const mismo = (a: string, b: string) => normalizar(a) === normalizar(b);

/** ¿El vehículo cumple lo que busca la persona? Si no, ¿está cerca y por qué? */
export function evaluar(v: VehiculoBase, c: Criterios): Evaluacion {
  const no: Evaluacion = { estado: 'no', motivos: [] };
  // Lo que no se negocia: marca, modelo y tipo.
  if (c.marca && !mismo(v.marca, c.marca)) return no;
  if (c.modelo && !mismo(v.modelo, c.modelo)) return no;
  if (c.tipo && v.tipo !== c.tipo) return no;

  const motivos: string[] = [];

  if (c.precioMax !== undefined && v.precio_usd > c.precioMax) {
    const dif = v.precio_usd - c.precioMax;
    if (dif > c.precioMax * TOLERANCIA.precio) return no;
    motivos.push(`${formatoUSD(dif)} por encima de tu presupuesto`);
  }
  if (c.precioMin !== undefined && v.precio_usd < c.precioMin) {
    const dif = c.precioMin - v.precio_usd;
    if (dif > c.precioMin * TOLERANCIA.precio) return no;
    motivos.push(`${formatoUSD(dif)} más barato de lo que buscás`);
  }
  if (c.kmMax !== undefined && v.km > c.kmMax) {
    const dif = v.km - c.kmMax;
    const tope = c.kmMax === 0 ? 1000 : c.kmMax * TOLERANCIA.km;
    if (dif > tope) return no;
    motivos.push(c.kmMax === 0 ? `Tiene ${formatoNumero(v.km)} km` : `${formatoNumero(dif)} km más de lo que buscás`);
  }
  if (c.anioMin !== undefined && v.anio < c.anioMin) {
    if (c.anioMin - v.anio > TOLERANCIA.anios) return no;
    motivos.push(`Es ${v.anio}, un año antes de lo que buscás`);
  }
  if (c.anioMax !== undefined && v.anio > c.anioMax) {
    if (v.anio - c.anioMax > TOLERANCIA.anios) return no;
    motivos.push(`Es ${v.anio}, un año más nuevo de lo que buscás`);
  }
  if (c.transmision && v.transmision !== c.transmision) motivos.push(v.transmision === 'manual' ? 'Es manual' : 'Es automática');
  if (c.combustible && v.combustible !== c.combustible) {
    motivos.push(v.combustible === 'nafta' ? 'Es a nafta' : `Es ${nombreCombustible(v.combustible).toLowerCase()}`);
  }
  if (c.traccion4x4 && !v.traccion_4x4) motivos.push('No es 4x4');

  if (motivos.length === 0) return { estado: 'coincide', motivos };
  if (motivos.length <= TOLERANCIA.maxMotivos) return { estado: 'casi', motivos };
  return no;
}

export type Resultado<V extends VehiculoBase = VehiculoBase> = {
  vehiculo: V;
  distanciaKm: number | null;
  motivos: string[];
};

export type Resultados<V extends VehiculoBase = VehiculoBase> = {
  coinciden: Resultado<V>[];
  casi: Resultado<V>[];
};

/**
 * Separa en "Coincide" y "Casi" y ordena. La ubicación nunca filtra: todos los
 * vehículos aparecen, primero los destacados y después los más cercanos.
 */
export function buscar<V extends VehiculoBase>(vehiculos: V[], c: Criterios, origen: Ubicacion | null): Resultados<V> {
  const ref = c.lugar ?? origen;
  const coinciden: Resultado<V>[] = [];
  const casi: Resultado<V>[] = [];
  for (const v of vehiculos) {
    const ev = evaluar(v, c);
    if (ev.estado === 'no') continue;
    const distanciaKm = ref ? Math.round(distanciaKm_(ref, v)) : null;
    (ev.estado === 'coincide' ? coinciden : casi).push({ vehiculo: v, distanciaKm, motivos: ev.motivos });
  }
  const orden = (a: Resultado<V>, b: Resultado<V>) => {
    const d = Number(!!b.vehiculo.destacado) - Number(!!a.vehiculo.destacado);
    if (d !== 0) return d;
    const da = a.distanciaKm ?? Infinity;
    const db = b.distanciaKm ?? Infinity;
    if (da !== db) return da - db;
    return (b.vehiculo.creado ?? '').localeCompare(a.vehiculo.creado ?? '');
  };
  coinciden.sort(orden);
  casi.sort((a, b) => a.motivos.length - b.motivos.length || orden(a, b));
  return { coinciden, casi };
}

function distanciaKm_(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  return distanciaKm(a.lat, a.lng, b.lat, b.lng);
}

/** Distancia entre una ubicación y un vehículo, redondeada. */
export function distanciaA(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  return Math.round(distanciaKm_(a, b));
}

// ═════════════════════════════ Textos de vehículos ═══════════════════════════

export function tituloVehiculo(v: Pick<VehiculoBase, 'marca' | 'modelo' | 'anio'>): string {
  return `${v.marca} ${v.modelo} ${v.anio}`;
}

/** Notificación para quien guardó la búsqueda. */
export function mensajeAlerta(v: VehiculoBase, distancia: number | null, desde: string | null): { titulo: string; cuerpo: string } {
  const lugar = nombreLugar(v.departamento, v.ciudad);
  const dist = distancia !== null && desde ? ` (${textoDistancia(distancia)} de ${desde})` : '';
  return {
    titulo: `🔔 Apareció un ${tituloVehiculo(v)}`,
    cuerpo: `${formatoUSD(v.precio_usd)} · ${formatoNumero(v.km)} km · 📍 ${lugar}${dist}`,
  };
}

/** Notificación para la automotora cuando aparece un cliente nuevo. */
export function mensajeClienteNuevo(c: Criterios, desde: string | null): { titulo: string; cuerpo: string } {
  return {
    titulo: '🧑 Nuevo cliente para tu inventario',
    cuerpo: `Busca ${resumenCriterios(c)}${desde ? ` · está en ${desde}` : ''}`,
  };
}

// ═════════════════════════════ Validación de publicaciones ═══════════════════

export const MAX_FOTOS = 10;

export type DatosPublicacion = {
  marca: string;
  modelo: string;
  anio: number;
  km: number;
  precio_usd: number;
  transmision: string;
  combustible: string;
  tipo: string;
  departamento: string;
  ciudad: string;
  fotos: number;
  contacto_nombre?: string;
  contacto_whatsapp?: string;
  esAutomotora?: boolean;
};

/** Devuelve la lista de problemas (vacía si está todo bien). */
export function validarPublicacion(d: DatosPublicacion): string[] {
  const e: string[] = [];
  if (d.fotos < 1) e.push('Agregá al menos una foto.');
  if (d.fotos > MAX_FOTOS) e.push(`Podés subir hasta ${MAX_FOTOS} fotos.`);
  if (!d.marca.trim()) e.push('Elegí la marca.');
  if (!d.modelo.trim()) e.push('Elegí el modelo.');
  if (!Number.isInteger(d.anio) || d.anio < AÑO_MIN || d.anio > anioActual() + 1) e.push('Revisá el año.');
  if (!Number.isFinite(d.km) || d.km < 0 || d.km > 2_000_000) e.push('Revisá los kilómetros.');
  if (!Number.isFinite(d.precio_usd) || d.precio_usd < 100 || d.precio_usd > 5_000_000) e.push('Revisá el precio en dólares.');
  if (!TRANSMISIONES.some((x) => x.id === d.transmision)) e.push('Elegí la transmisión.');
  if (!COMBUSTIBLES.some((x) => x.id === d.combustible)) e.push('Elegí el combustible.');
  if (!TIPOS.some((x) => x.id === d.tipo)) e.push('Elegí el tipo.');
  if (!ubicacionDe(d.departamento, d.ciudad)) e.push('Elegí departamento y ciudad.');
  if (!d.esAutomotora) {
    if (!d.contacto_nombre?.trim()) e.push('Escribí tu nombre.');
    if (!whatsappValido(d.contacto_whatsapp ?? '')) e.push('Escribí un WhatsApp válido (ej.: 099 123 456).');
  }
  return e;
}

/** Acepta 09X XXX XXX, 9X XXX XXX o +598 9X XXX XXX. */
export function whatsappValido(tel: string): boolean {
  return normalizarWhatsapp(tel) !== null;
}

/** Devuelve el número en formato internacional sin "+": "59899123456". */
export function normalizarWhatsapp(tel: string): string | null {
  const d = tel.replace(/\D/g, '');
  if (/^5989\d{7}$/.test(d)) return d;
  if (/^09\d{7}$/.test(d)) return '598' + d.slice(1);
  if (/^9\d{7}$/.test(d)) return '598' + d;
  // Teléfonos fijos (2XXX XXXX / 4XXX XXXX) sirven para llamar.
  if (/^[24]\d{7}$/.test(d)) return '598' + d;
  if (/^598[24]\d{7}$/.test(d)) return d;
  return null;
}
