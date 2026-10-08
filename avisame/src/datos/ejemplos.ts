// Vehículos y búsquedas de EJEMPLO para la vista previa. No son reales.
import { ubicacionDe, type Combustible, type Tipo, type Transmision } from '../nucleo';
import type { Busqueda, Vehiculo } from './tipos';

type Fila = [
  marca: string, modelo: string, version: string, anio: number, km: number, precio: number,
  transmision: Transmision, combustible: Combustible, tipo: Tipo, x4: boolean,
  departamento: string, ciudad: string, color: string, automotora?: 'costa' | 'litoral',
];

// Las fotos de ejemplo son ilustraciones: "demo:<tipo>:<color>".
const FILAS: Fila[] = [
  ['Hyundai', 'Creta', '1.6 Limited', 2023, 38000, 17500, 'automatica', 'nafta', 'suv', false, 'Canelones', 'Atlántida', '#B91C1C'],
  ['Hyundai', 'Creta', '1.6 Comfort', 2022, 61000, 18900, 'automatica', 'nafta', 'suv', false, 'Montevideo', 'Montevideo', '#E5E7EB', 'costa'],
  ['Hyundai', 'Creta', '1.6 Smart', 2022, 52000, 16900, 'manual', 'nafta', 'suv', false, 'Salto', 'Salto', '#1F2937'],
  ['Toyota', 'Corolla', '2.0 XEi CVT', 2021, 45000, 19800, 'automatica', 'nafta', 'sedan', false, 'Maldonado', 'Maldonado', '#9CA3AF', 'costa'],
  ['Toyota', 'Corolla', '1.8 Híbrido', 2022, 30000, 23500, 'automatica', 'hibrido', 'sedan', false, 'Montevideo', 'Montevideo', '#F9FAFB'],
  ['Toyota', 'Hilux', '2.8 SRV 4x4', 2020, 98000, 36500, 'automatica', 'diesel', 'pickup', true, 'Tacuarembó', 'Tacuarembó', '#6B7280'],
  ['Toyota', 'Hilux', '2.4 DX 4x2', 2019, 120000, 27900, 'manual', 'diesel', 'pickup', false, 'Paysandú', 'Paysandú', '#F3F4F6', 'litoral'],
  ['Volkswagen', 'Gol', '1.6 Trendline', 2018, 89000, 9900, 'manual', 'nafta', 'hatch', false, 'Canelones', 'Las Piedras', '#DC2626'],
  ['Volkswagen', 'Amarok', '2.0 Highline 4x4', 2021, 75000, 39900, 'automatica', 'diesel', 'pickup', true, 'Rivera', 'Rivera', '#111827'],
  ['Volkswagen', 'T-Cross', '1.0 TSI Comfortline', 2022, 41000, 22900, 'automatica', 'nafta', 'suv', false, 'Montevideo', 'Montevideo', '#2563EB', 'costa'],
  ['Chevrolet', 'Onix', '1.0 LT', 2021, 52000, 13900, 'manual', 'nafta', 'hatch', false, 'Montevideo', 'Montevideo', '#E5E7EB'],
  ['Chevrolet', 'Onix Plus', '1.0 Turbo Premier', 2022, 33000, 17200, 'automatica', 'nafta', 'sedan', false, 'Florida', 'Florida', '#374151'],
  ['Chevrolet', 'Tracker', '1.2 Turbo LTZ', 2023, 21000, 26500, 'automatica', 'nafta', 'suv', false, 'Colonia', 'Colonia del Sacramento', '#991B1B'],
  ['Chevrolet', 'S10', '2.8 LTZ 4x4', 2018, 140000, 28500, 'automatica', 'diesel', 'pickup', true, 'Cerro Largo', 'Melo', '#9CA3AF'],
  ['Fiat', 'Cronos', '1.3 Drive', 2022, 47000, 14500, 'manual', 'nafta', 'sedan', false, 'San José', 'San José de Mayo', '#F9FAFB'],
  ['Fiat', 'Strada', '1.3 Freedom', 2023, 18000, 19900, 'manual', 'nafta', 'pickup', false, 'Durazno', 'Durazno', '#B91C1C', 'litoral'],
  ['Fiat', 'Mobi', '1.0 Like', 2020, 61000, 8900, 'manual', 'nafta', 'hatch', false, 'Lavalleja', 'Minas', '#F59E0B'],
  ['Renault', 'Duster', '1.6 Intens 4x4', 2020, 82000, 17900, 'manual', 'nafta', 'suv', true, 'Rocha', 'Rocha', '#78350F'],
  ['Renault', 'Kangoo', '1.6 Furgón', 2019, 110000, 12900, 'manual', 'nafta', 'utilitario', false, 'Montevideo', 'Montevideo', '#F3F4F6'],
  ['Peugeot', '208', '1.6 Allure', 2021, 39000, 16500, 'automatica', 'nafta', 'hatch', false, 'Maldonado', 'Punta del Este', '#1D4ED8', 'costa'],
  ['Peugeot', '2008', '1.6 Active', 2020, 58000, 17800, 'manual', 'nafta', 'suv', false, 'Soriano', 'Mercedes', '#6B7280'],
  ['Suzuki', 'Swift', '1.2 GL', 2019, 64000, 11900, 'manual', 'nafta', 'hatch', false, 'Artigas', 'Artigas', '#DC2626'],
  ['Suzuki', 'Vitara', '1.6 GLX AllGrip', 2021, 49000, 23900, 'automatica', 'nafta', 'suv', true, 'Treinta y Tres', 'Treinta y Tres', '#065F46'],
  ['Kia', 'Sportage', '2.0 EX', 2019, 91000, 21500, 'automatica', 'nafta', 'suv', false, 'Río Negro', 'Fray Bentos', '#E5E7EB', 'litoral'],
  ['Nissan', 'Frontier', '2.3 LE 4x4', 2022, 54000, 37900, 'automatica', 'diesel', 'pickup', true, 'Flores', 'Trinidad', '#4B5563'],
  ['Nissan', 'Kicks', '1.6 Advance CVT', 2022, 36000, 19500, 'automatica', 'nafta', 'suv', false, 'Canelones', 'Ciudad de la Costa', '#C2410C'],
  ['BYD', 'Dolphin Mini', 'GL', 2024, 9000, 21900, 'automatica', 'electrico', 'hatch', false, 'Montevideo', 'Montevideo', '#38BDF8', 'costa'],
  ['Ford', 'Ranger', '3.2 XLT 4x4', 2019, 115000, 33500, 'automatica', 'diesel', 'pickup', true, 'Salto', 'Salto', '#1F2937', 'litoral'],
  ['Citroën', 'C3', '1.2 Feel', 2023, 15000, 15900, 'manual', 'nafta', 'hatch', false, 'Canelones', 'Pando', '#F9FAFB'],
  ['Chery', 'Tiggo 4', '1.5 Pro', 2023, 22000, 18900, 'automatica', 'nafta', 'suv', false, 'Paysandú', 'Paysandú', '#7F1D1D'],
];

export const AUTOMOTORAS_EJEMPLO = {
  costa: { id: 'auto-costa', nombre: 'Costa Este Autos (ejemplo)', telefono: '42001122', destacada: true },
  litoral: { id: 'auto-litoral', nombre: 'Litoral Motors (ejemplo)', telefono: '47224455', destacada: false },
};

const NOMBRES = ['Martín', 'Lucía', 'Sofía', 'Diego', 'Valentina', 'Joaquín', 'Florencia', 'Nicolás', 'Camila', 'Federico'];

export function vehiculosEjemplo(): Vehiculo[] {
  const ahora = Date.now();
  return FILAS.map((f, i) => {
    const [marca, modelo, version, anio, km, precio, transmision, combustible, tipo, x4, departamento, ciudad, color, auto] = f;
    const u = ubicacionDe(departamento, ciudad)!;
    const a = auto ? AUTOMOTORAS_EJEMPLO[auto] : null;
    return {
      id: `ej-${i + 1}`,
      owner_id: a ? `duenio-${auto}` : `vendedor-${i + 1}`,
      automotora_id: a?.id ?? null,
      source: a ? 'automotora' : 'avisame',
      external_id: null,
      external_url: null,
      marca, modelo, version, anio, km, precio_usd: precio, transmision, combustible, tipo, traccion_4x4: x4,
      descripcion: `${marca} ${modelo} ${version} en muy buen estado. Service al día, papeles en regla. Vehículo de ejemplo de la vista previa.`,
      departamento: u.departamento,
      ciudad: u.ciudad,
      direccion: null,
      // Un pequeño corrimiento para que no queden todos en el mismo punto.
      lat: u.lat + ((i % 5) - 2) * 0.004,
      lng: u.lng + ((i % 3) - 1) * 0.004,
      fotos: [`demo:${tipo}:${color}`, `demo:${tipo}:${color}:interior`],
      contacto_nombre: a?.nombre ?? NOMBRES[i % NOMBRES.length],
      contacto_whatsapp: a?.telefono ?? `0991${String(10000 + i * 137).slice(-5)}`,
      estado: 'activo',
      creado: new Date(ahora - i * 7 * 3600_000).toISOString(),
      destacado: a?.destacada ?? false,
      automotora_nombre: a?.nombre ?? null,
    };
  });
}

/** Personas de ejemplo que guardaron búsquedas (para el panel de automotoras). */
export function busquedasEjemplo(): (Busqueda & { user_id: string })[] {
  const filas: [string, string, string, boolean][] = [
    ['Hyundai Creta 2021 o más nueva hasta USD 20.000', 'Canelones', 'Pando', true],
    ['Toyota Corolla automático', 'Maldonado', 'San Carlos', true],
    ['T-Cross hasta 25 mil dólares', 'Montevideo', 'Montevideo', false],
    ['Peugeot 208 2020 o más nuevo', 'Rocha', 'La Paloma', true],
    ['Toyota Hilux 4x4 diésel', 'Durazno', 'Sarandí del Yí', true],
    ['BYD Dolphin Mini eléctrico', 'Canelones', 'Ciudad de la Costa', false],
  ];
  return filas.map(([texto, dep, ciu, autoriza], i) => {
    const u = ubicacionDe(dep, ciu)!;
    return {
      id: `bus-ej-${i + 1}`,
      user_id: `persona-${i + 1}`,
      texto,
      criterios: {},
      nombre: NOMBRES[(i + 3) % NOMBRES.length],
      whatsapp: `0982${String(30000 + i * 911).slice(-5)}`,
      autoriza_contacto: autoriza,
      departamento: u.departamento,
      ciudad: u.ciudad,
      lat: u.lat,
      lng: u.lng,
      activa: true,
      creado: new Date(Date.now() - (i + 1) * 26 * 3600_000).toISOString(),
    };
  });
}
