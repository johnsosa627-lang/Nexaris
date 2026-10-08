// Pruebas del núcleo. Se corren con: npm run test:nucleo
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  interpretar,
  etiquetas,
  quitarCriterio,
  textoDesdeCriterios,
  evaluar,
  buscar,
  distanciaA,
  ubicacionDe,
  avisoLejos,
  ciudadMasCercana,
  planVigente,
  normalizarWhatsapp,
  validarPublicacion,
  DEPARTAMENTOS,
  type VehiculoBase,
  type Criterios,
} from '../supabase/functions/_shared/nucleo.ts';

test('interpreta la búsqueda del ejemplo', () => {
  const c = interpretar('Busco una Hyundai Creta 2022 o más nueva, menos de 70.000 km y hasta 18.000 dólares');
  assert.deepEqual(c, { marca: 'Hyundai', modelo: 'Creta', anioMin: 2022, kmMax: 70000, precioMax: 18000 });
});

test('interpreta transmisión, combustible, tipo, 4x4 y lugar', () => {
  const c = interpretar('pickup diesel 4x4 automática hasta USD 30.000 en Salto');
  assert.equal(c.tipo, 'pickup');
  assert.equal(c.combustible, 'diesel');
  assert.equal(c.traccion4x4, true);
  assert.equal(c.transmision, 'automatica');
  assert.equal(c.precioMax, 30000);
  assert.equal(c.lugar?.ciudad, 'Salto');
});

test('marca por alias y modelo que implica la marca', () => {
  assert.deepEqual(interpretar('vw gol'), { marca: 'Volkswagen', modelo: 'Gol' });
  assert.deepEqual(interpretar('hilux'), { marca: 'Toyota', modelo: 'Hilux' });
  assert.deepEqual(interpretar('Peugeot 208 2019'), { marca: 'Peugeot', modelo: '208', anioMin: 2019, anioMax: 2019 });
  // "208" sin marca no es un modelo
  assert.equal(interpretar('208').modelo, undefined);
  // "uno" sin marca no es el Fiat Uno
  assert.equal(interpretar('busco uno automático').modelo, undefined);
});

test('rangos de años y precios', () => {
  assert.deepEqual(interpretar('corolla entre 2015 y 2019'), { marca: 'Toyota', modelo: 'Corolla', anioMin: 2015, anioMax: 2019 });
  assert.deepEqual(interpretar('suv entre 15 mil y 20 mil dolares'), { tipo: 'suv', precioMin: 15000, precioMax: 20000 });
  assert.deepEqual(interpretar('onix desde 2018 hasta 12000'), { marca: 'Chevrolet', modelo: 'Onix', anioMin: 2018, precioMax: 12000 });
  assert.deepEqual(interpretar('gol hasta 2012'), { marca: 'Volkswagen', modelo: 'Gol', anioMax: 2012 });
  assert.deepEqual(interpretar('auto 0km'), { kmMax: 0 });
  assert.deepEqual(interpretar('u$s 9500 nafta'), { precioMax: 9500, combustible: 'nafta' });
});

test('"Mercedes" es marca, "en Mercedes" es lugar', () => {
  assert.equal(interpretar('mercedes clase c').marca, 'Mercedes-Benz');
  const c = interpretar('hilux en mercedes');
  assert.equal(c.lugar?.ciudad, 'Mercedes');
  assert.equal(c.lugar?.departamento, 'Soriano');
  assert.equal(interpretar('Kia Rio en Río Negro').modelo, 'Rio');
  assert.equal(interpretar('Kia Rio en Río Negro').lugar?.departamento, 'Río Negro');
});

test('etiquetas, quitar y volver a escribir la frase', () => {
  const c = interpretar('Toyota Corolla automático hasta 20 mil dólares en Maldonado');
  assert.deepEqual(etiquetas(c).map((e) => e.texto), ['Toyota Corolla', 'Hasta USD 20.000', 'Automática', '📍 Maldonado']);
  const sinPrecio = quitarCriterio(c, 'precio');
  assert.equal(sinPrecio.precioMax, undefined);
  const casos: string[] = [
    'Busco una Hyundai Creta 2022 o más nueva, menos de 70.000 km y hasta 18.000 dólares',
    'pickup diesel 4x4 automática hasta USD 30.000 en Salto',
    'corolla entre 2015 y 2019 entre 10 mil y 15 mil dolares',
    'Peugeot 208 2019 0km',
  ];
  for (const t of casos) {
    const a = interpretar(t);
    assert.deepEqual(interpretar(textoDesdeCriterios(a)), a, `ida y vuelta: ${t} → ${textoDesdeCriterios(a)}`);
  }
});

const montevideo = ubicacionDe('Montevideo')!;
const salto = ubicacionDe('Salto', 'Salto')!;
const atlantida = ubicacionDe('Canelones', 'Atlántida')!;

function vehiculo(p: Partial<VehiculoBase>): VehiculoBase {
  return {
    marca: 'Hyundai', modelo: 'Creta', anio: 2023, km: 40000, precio_usd: 17500, transmision: 'automatica',
    combustible: 'nafta', tipo: 'suv', traccion_4x4: false, departamento: 'Canelones', ciudad: 'Atlántida',
    lat: atlantida.lat, lng: atlantida.lng, ...p,
  };
}

test('coincide y casi, con motivos', () => {
  const c: Criterios = { marca: 'Hyundai', modelo: 'Creta', anioMin: 2022, kmMax: 70000, precioMax: 18000, transmision: 'automatica' };
  assert.deepEqual(evaluar(vehiculo({}), c), { estado: 'coincide', motivos: [] });
  assert.deepEqual(evaluar(vehiculo({ precio_usd: 18900 }), c), { estado: 'casi', motivos: ['USD 900 por encima de tu presupuesto'] });
  assert.deepEqual(evaluar(vehiculo({ transmision: 'manual' }), c), { estado: 'casi', motivos: ['Es manual'] });
  assert.equal(evaluar(vehiculo({ precio_usd: 25000 }), c).estado, 'no');
  assert.equal(evaluar(vehiculo({ modelo: 'Tucson' }), c).estado, 'no');
  assert.equal(evaluar(vehiculo({ anio: 2019 }), c).estado, 'no');
  assert.equal(evaluar(vehiculo({ precio_usd: 18900, transmision: 'manual', km: 80000 }), c).estado, 'no');
});

test('la ubicación nunca filtra y los cercanos van primero', () => {
  const lejos = vehiculo({ departamento: 'Salto', ciudad: 'Salto', lat: salto.lat, lng: salto.lng });
  const cerca = vehiculo({});
  const r = buscar([lejos, cerca], {}, montevideo);
  assert.equal(r.coinciden.length, 2);
  assert.equal(r.coinciden[0].vehiculo, cerca);
  // Los destacados van primero aunque estén más lejos.
  const r2 = buscar([cerca, { ...lejos, destacado: true }], {}, montevideo);
  assert.equal(r2.coinciden[0].vehiculo.ciudad, 'Salto');
  // Un lugar en la búsqueda cambia el punto de referencia.
  const r3 = buscar([cerca, lejos], { lugar: salto }, montevideo);
  assert.equal(r3.coinciden[0].vehiculo, lejos);
  assert.equal(r3.coinciden[0].distanciaKm, 0);
});

test('distancias y aviso de lejanía', () => {
  const d = distanciaA(atlantida, salto);
  assert.ok(d >= 420 && d <= 440, `Atlántida–Salto: ${d}`);
  assert.equal(avisoLejos(d, 'Salto'), `⚠️ Está lejos: a ${d} km de Salto`);
  assert.equal(avisoLejos(40, 'Montevideo'), null);
  assert.equal(ciudadMasCercana(-34.9, -56.17).ciudad, 'Montevideo');
});

test('19 departamentos con coordenadas dentro de Uruguay', () => {
  assert.equal(DEPARTAMENTOS.length, 19);
  for (const d of DEPARTAMENTOS) {
    assert.ok(d.ciudades.length > 0);
    for (const c of d.ciudades) {
      assert.ok(c.lat < -30 && c.lat > -35.1 && c.lng < -53.1 && c.lng > -58.5, `${c.nombre}`);
    }
  }
});

test('planes y vencimientos', () => {
  const futuro = new Date(Date.now() + 86400000).toISOString();
  const pasado = new Date(Date.now() - 86400000).toISOString();
  assert.equal(planVigente('pro', futuro), 'pro');
  assert.equal(planVigente('pro', pasado), 'gratis');
  assert.equal(planVigente('destacado', null), 'gratis');
  assert.equal(planVigente('cualquiera', futuro), 'gratis');
});

test('whatsapp y validación', () => {
  assert.equal(normalizarWhatsapp('099 123 456'), '59899123456');
  assert.equal(normalizarWhatsapp('+598 98 765 432'), '59898765432');
  assert.equal(normalizarWhatsapp('123'), null);
  const ok = validarPublicacion({
    marca: 'Toyota', modelo: 'Corolla', anio: 2020, km: 50000, precio_usd: 20000, transmision: 'automatica',
    combustible: 'nafta', tipo: 'sedan', departamento: 'Salto', ciudad: 'Salto', fotos: 3, contacto_nombre: 'Ana', contacto_whatsapp: '099123456',
  });
  assert.deepEqual(ok, []);
  const mal = validarPublicacion({
    marca: '', modelo: '', anio: 1800, km: -1, precio_usd: 0, transmision: 'x', combustible: 'x', tipo: 'x', departamento: 'X', ciudad: 'Y', fotos: 0,
  });
  assert.ok(mal.length >= 10);
});
