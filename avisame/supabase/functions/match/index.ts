// match: cruza vehículos con búsquedas guardadas y avisa al celular.
//
// POST { vehiculo_id }  → se llama al publicar o editar un vehículo.
//                         Avisa a quienes lo estaban buscando.
// POST { busqueda_id }  → se llama al guardar una búsqueda.
//                         Registra lo que ya coincide y avisa a las automotoras.
//
// Cada par búsqueda–vehículo se guarda una sola vez (tabla coincidencias), así
// nunca se repite un aviso. Lo mismo para las automotoras (avisos_automotora).
import type { SupabaseClient } from 'npm:@supabase/supabase-js@2';
import { admin, enviarPush, error, json, servir, usuario, type Push } from '../_shared/servidor.ts';
import {
  distanciaA,
  evaluar,
  mensajeAlerta,
  mensajeClienteNuevo,
  nombreLugar,
  planVigente,
  PLANES,
  type Criterios,
  type VehiculoBase,
} from '../_shared/nucleo.ts';

type Vehiculo = VehiculoBase & { id: string; owner_id: string | null; automotora_id: string | null; estado: string };
type Busqueda = {
  id: string;
  user_id: string;
  criterios: Criterios;
  departamento: string;
  ciudad: string;
  lat: number;
  lng: number;
};

const LOTE = 1000;

servir(async (req) => {
  if (req.method !== 'POST') return error('Método no permitido', 405);
  const db = admin();
  const yo = await usuario(req, db);
  if (!yo) return error('Tenés que ingresar', 401);
  const cuerpo = await req.json().catch(() => ({}));

  if (typeof cuerpo.vehiculo_id === 'string') return json(await porVehiculo(db, cuerpo.vehiculo_id));
  if (typeof cuerpo.busqueda_id === 'string') {
    const { data: b } = await db.from('busquedas').select('user_id').eq('id', cuerpo.busqueda_id).maybeSingle();
    if (!b || b.user_id !== yo.id) return error('Búsqueda no encontrada', 404);
    return json(await porBusqueda(db, cuerpo.busqueda_id));
  }
  return error('Falta vehiculo_id o busqueda_id');
});

async function porVehiculo(db: SupabaseClient, id: string) {
  const { data: v } = await db.from('vehiculos').select('*').eq('id', id).maybeSingle<Vehiculo>();
  if (!v || v.estado !== 'activo') return { nuevas: 0 };

  const candidatas: { b: Busqueda; distancia: number }[] = [];
  for (let desde = 0; ; desde += LOTE) {
    const { data, error: e } = await db
      .from('busquedas')
      .select('id, user_id, criterios, departamento, ciudad, lat, lng')
      .eq('activa', true)
      .order('creado')
      .range(desde, desde + LOTE - 1);
    if (e) throw e;
    for (const b of (data ?? []) as Busqueda[]) {
      if (b.user_id === v.owner_id) continue;
      if (evaluar(v, b.criterios).estado === 'coincide') candidatas.push({ b, distancia: distanciaA(b, v) });
    }
    if (!data || data.length < LOTE) break;
  }
  if (candidatas.length === 0) return { nuevas: 0 };

  const nuevas = await registrar(
    db,
    candidatas.map(({ b, distancia }) => ({ busqueda_id: b.id, vehiculo_id: v.id, user_id: b.user_id, distancia_km: distancia })),
  );

  // Aviso a cada persona por cada coincidencia nueva.
  const tokens = await tokensDe(db, nuevas.map((n) => n.user_id));
  const mensajes: Push[] = [];
  for (const n of nuevas) {
    const b = candidatas.find((x) => x.b.id === n.busqueda_id)!.b;
    const token = tokens.get(n.user_id);
    if (!token) continue;
    const m = mensajeAlerta(v, n.distancia_km, nombreLugar(b.departamento, b.ciudad));
    mensajes.push({ to: token, title: m.titulo, body: m.cuerpo, data: { tipo: 'alerta', vehiculo_id: v.id } });
  }
  await enviarPush(mensajes);
  if (nuevas.length) await db.from('coincidencias').update({ avisado: true }).in('id', nuevas.map((n) => n.id));

  if (v.automotora_id) {
    await avisarAutomotora(db, v.automotora_id, candidatas.filter((c) => nuevas.some((n) => n.busqueda_id === c.b.id)).map((c) => c.b));
  }
  return { nuevas: nuevas.length };
}

async function porBusqueda(db: SupabaseClient, id: string) {
  const { data: b } = await db.from('busquedas').select('id, user_id, criterios, departamento, ciudad, lat, lng').eq('id', id).maybeSingle<Busqueda>();
  if (!b) return { nuevas: 0 };
  const c = b.criterios;

  const encontrados: Vehiculo[] = [];
  for (let desde = 0; ; desde += LOTE) {
    let q = db.from('vehiculos').select('*').eq('estado', 'activo');
    if (c.marca) q = q.ilike('marca', escapar(c.marca));
    if (c.modelo) q = q.ilike('modelo', escapar(c.modelo));
    if (c.tipo) q = q.eq('tipo', c.tipo);
    const { data, error: e } = await q.order('creado').range(desde, desde + LOTE - 1);
    if (e) throw e;
    for (const v of (data ?? []) as Vehiculo[]) {
      if (v.owner_id !== b.user_id && evaluar(v, c).estado === 'coincide') encontrados.push(v);
    }
    if (!data || data.length < LOTE) break;
  }
  if (encontrados.length === 0) return { nuevas: 0 };

  // Lo que ya estaba publicado no se avisa (la persona ya lo vio en los resultados).
  const nuevas = await registrar(
    db,
    encontrados.map((v) => ({ busqueda_id: b.id, vehiculo_id: v.id, user_id: b.user_id, distancia_km: distanciaA(b, v), avisado: true, vista: true })),
  );

  const automotoras = new Set(encontrados.map((v) => v.automotora_id).filter((x): x is string => !!x));
  for (const a of automotoras) await avisarAutomotora(db, a, [b]);
  return { nuevas: nuevas.length };
}

type Fila = { busqueda_id: string; vehiculo_id: string; user_id: string; distancia_km: number; avisado?: boolean; vista?: boolean };

/** Inserta coincidencias; devuelve solo las que no existían. */
async function registrar(db: SupabaseClient, filas: Fila[]) {
  const { data, error: e } = await db
    .from('coincidencias')
    .upsert(filas, { onConflict: 'busqueda_id,vehiculo_id', ignoreDuplicates: true })
    .select('id, busqueda_id, user_id, distancia_km');
  if (e) throw e;
  return (data ?? []) as { id: string; busqueda_id: string; user_id: string; distancia_km: number }[];
}

/** "Nuevo cliente" a la automotora, una sola vez por búsqueda y con plan Pro o Destacado (o en el lanzamiento). */
async function avisarAutomotora(db: SupabaseClient, automotoraId: string, busquedas: Busqueda[]) {
  if (busquedas.length === 0) return;
  const { data: a } = await db.from('automotoras').select('id, owner_id, plan, plan_vence').eq('id', automotoraId).maybeSingle();
  if (!a) return;
  const { data: nuevos } = await db
    .from('avisos_automotora')
    .upsert(busquedas.map((b) => ({ automotora_id: a.id, busqueda_id: b.id })), { onConflict: 'automotora_id,busqueda_id', ignoreDuplicates: true })
    .select('busqueda_id');
  if (!nuevos?.length) return;
  // En el modo lanzamiento (sin cobros) todas las automotoras reciben los avisos.
  const { data: cobros } = await db.rpc('cobros_activos');
  if (cobros !== false && !PLANES[planVigente(a.plan, a.plan_vence)].avisos) return;
  const token = (await tokensDe(db, [a.owner_id])).get(a.owner_id);
  if (!token) return;
  await enviarPush(
    nuevos.map((n: { busqueda_id: string }) => {
      const b = busquedas.find((x) => x.id === n.busqueda_id)!;
      const m = mensajeClienteNuevo(b.criterios, nombreLugar(b.departamento, b.ciudad));
      return { to: token, title: m.titulo, body: m.cuerpo, data: { tipo: 'cliente', busqueda_id: b.id } };
    }),
  );
}

async function tokensDe(db: SupabaseClient, ids: string[]): Promise<Map<string, string>> {
  const unicos = [...new Set(ids)];
  if (unicos.length === 0) return new Map();
  const { data } = await db.from('perfiles').select('id, push_token').in('id', unicos).not('push_token', 'is', null);
  return new Map((data ?? []).map((p: { id: string; push_token: string }) => [p.id, p.push_token]));
}

/** Para ilike: que "%" y "_" se busquen literalmente. */
function escapar(s: string): string {
  return s.replace(/[\\%_]/g, (x) => '\\' + x);
}
