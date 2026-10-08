import 'react-native-url-polyfill/auto';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { createClient, FunctionsHttpError, type SupabaseClient } from '@supabase/supabase-js';
import { Platform } from 'react-native';
import { TOLERANCIA, ubicacionDe, type Criterios } from '../nucleo';
import { subirFoto } from '../servicios/fotos';
import type { Api } from './api';
import type { Alerta, Automotora, Cliente, RegistroPago, Usuario, Vehiculo } from './tipos';

const BUCKET = 'fotos';

export function crearApiSupabase(url: string, clave: string): Api {
  const sb: SupabaseClient = createClient(url, clave, {
    auth: {
      storage: Platform.OS === 'web' ? undefined : AsyncStorage,
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: false,
    },
  });

  const aUsuario = (u: { id: string; email?: string } | null | undefined): Usuario | null =>
    u ? { id: u.id, email: u.email ?? '' } : null;

  async function yo(): Promise<Usuario> {
    const { data } = await sb.auth.getSession();
    const u = aUsuario(data.session?.user);
    if (!u) throw new Error('Tenés que ingresar con tu email.');
    return u;
  }

  /** Llama a una función del servidor y devuelve su mensaje de error en español. */
  async function funcion<T>(nombre: string, body?: unknown): Promise<T> {
    const { data, error } = await sb.functions.invoke(nombre, { body: body ?? {} });
    if (error) {
      if (error instanceof FunctionsHttpError) {
        const detalle = await error.context.json().catch(() => null);
        if (detalle?.error) throw new Error(detalle.error);
      }
      throw new Error('No pudimos conectarnos. Revisá tu conexión.');
    }
    return data as T;
  }

  function lanzar(error: { message: string } | null) {
    if (error) throw new Error(error.message);
  }

  const urlPublica = sb.storage.from(BUCKET).getPublicUrl('').data.publicUrl;
  const rutaDeUrl = (u: string) => (u.startsWith(urlPublica) ? decodeURIComponent(u.slice(urlPublica.length).replace(/^\//, '')) : null);

  return {
    vistaPrevia: false,

    async usuario() {
      const { data } = await sb.auth.getSession();
      return aUsuario(data.session?.user);
    },
    escucharSesion(cb) {
      const { data } = sb.auth.onAuthStateChange((_e, s) => cb(aUsuario(s?.user)));
      return () => data.subscription.unsubscribe();
    },
    async pedirCodigo(email) {
      const { error } = await sb.auth.signInWithOtp({ email: email.trim().toLowerCase(), options: { shouldCreateUser: true } });
      lanzar(error);
    },
    async verificarCodigo(email, codigo) {
      const { error } = await sb.auth.verifyOtp({ email: email.trim().toLowerCase(), token: codigo.trim(), type: 'email' });
      if (error) throw new Error('El código no es correcto o ya venció. Pedí uno nuevo.');
    },
    async salir() {
      await sb.auth.signOut();
    },
    async borrarCuenta() {
      await funcion('delete-account');
      await sb.auth.signOut();
    },
    async guardarPushToken(token) {
      const u = await yo();
      lanzar((await sb.from('perfiles').update({ push_token: token }).eq('id', u.id)).error);
    },

    async buscarVehiculos(c: Criterios) {
      let q = sb.from('vehiculos_publicos').select('*');
      // Solo lo que no se negocia filtra en la base; el resto (y los "Casi") lo decide el núcleo.
      if (c.marca) q = q.ilike('marca', escaparLike(c.marca));
      if (c.modelo) q = q.ilike('modelo', escaparLike(c.modelo));
      if (c.tipo) q = q.eq('tipo', c.tipo);
      if (c.precioMax !== undefined) q = q.lte('precio_usd', Math.ceil(c.precioMax * (1 + TOLERANCIA.precio)));
      if (c.anioMin !== undefined) q = q.gte('anio', c.anioMin - TOLERANCIA.anios);
      if (c.anioMax !== undefined) q = q.lte('anio', c.anioMax + TOLERANCIA.anios);
      const { data, error } = await q.order('creado', { ascending: false }).limit(500);
      lanzar(error);
      return (data ?? []) as Vehiculo[];
    },
    async vehiculo(id) {
      const pub = await sb.from('vehiculos_publicos').select('*').eq('id', id).maybeSingle();
      if (pub.data) return pub.data as Vehiculo;
      const propio = await sb.from('vehiculos').select('*').eq('id', id).maybeSingle();
      return (propio.data as Vehiculo) ?? null;
    },
    async misVehiculos() {
      const u = await yo();
      const { data, error } = await sb.from('vehiculos').select('*').eq('owner_id', u.id).order('creado', { ascending: false });
      lanzar(error);
      return (data ?? []) as Vehiculo[];
    },
    async guardarVehiculo(datos, fotos, { id, automotoraId }) {
      const u = await yo();
      const carpeta = `${u.id}/${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
      const urls: string[] = [];
      for (let i = 0; i < fotos.length; i++) {
        const f = fotos[i];
        if (/^https?:\/\//.test(f)) urls.push(f);
        else urls.push(await subirFoto(sb, BUCKET, `${carpeta}/${i}.jpg`, f));
      }
      const lugar = ubicacionDe(datos.departamento, datos.ciudad);
      const fila = {
        ...datos,
        version: datos.version.trim() || null,
        descripcion: datos.descripcion.trim() || null,
        direccion: datos.direccion.trim() || null,
        lat: lugar?.lat,
        lng: lugar?.lng,
        fotos: urls,
      };
      let vehiculoId = id;
      if (id) {
        const anterior = await sb.from('vehiculos').select('fotos').eq('id', id).single();
        lanzar((await sb.from('vehiculos').update(fila).eq('id', id)).error);
        const sobran = ((anterior.data?.fotos ?? []) as string[]).filter((x) => !urls.includes(x)).map(rutaDeUrl).filter((x): x is string => !!x);
        if (sobran.length) await sb.storage.from(BUCKET).remove(sobran);
      } else {
        const { data, error } = await sb
          .from('vehiculos')
          .insert({ ...fila, owner_id: u.id, automotora_id: automotoraId ?? null, source: automotoraId ? 'automotora' : 'avisame' })
          .select('id')
          .single();
        lanzar(error);
        vehiculoId = data!.id as string;
      }
      // Avisar a quienes lo están buscando. Si falla, la publicación igual queda.
      funcion('match', { vehiculo_id: vehiculoId }).catch(() => {});
      return vehiculoId!;
    },
    async cambiarEstado(id, estado) {
      lanzar((await sb.from('vehiculos').update({ estado }).eq('id', id)).error);
      if (estado === 'activo') funcion('match', { vehiculo_id: id }).catch(() => {});
    },
    async borrarVehiculo(id) {
      const { data } = await sb.from('vehiculos').select('fotos').eq('id', id).single();
      lanzar((await sb.from('vehiculos').delete().eq('id', id)).error);
      const rutas = ((data?.fotos ?? []) as string[]).map(rutaDeUrl).filter((x): x is string => !!x);
      if (rutas.length) await sb.storage.from(BUCKET).remove(rutas);
    },
    async denunciar(vehiculoId, motivo, detalle) {
      const { data } = await sb.auth.getSession();
      const { error } = await sb.from('denuncias').insert({
        vehiculo_id: vehiculoId,
        user_id: data.session?.user.id ?? null,
        motivo,
        detalle: detalle.trim() || null,
      });
      lanzar(error);
    },

    async guardarBusqueda(b) {
      const u = await yo();
      const { data, error } = await sb.from('busquedas').insert({ ...b, user_id: u.id }).select('id').single();
      lanzar(error);
      funcion('match', { busqueda_id: data!.id }).catch(() => {});
    },
    async misBusquedas() {
      const { data, error } = await sb.from('busquedas').select('*').order('creado', { ascending: false });
      lanzar(error);
      return data ?? [];
    },
    async borrarBusqueda(id) {
      lanzar((await sb.from('busquedas').delete().eq('id', id)).error);
    },
    async alertas() {
      const { data, error } = await sb
        .from('coincidencias')
        .select('id, busqueda_id, distancia_km, vista, creado, vehiculo:vehiculos(*)')
        .order('creado', { ascending: false })
        .limit(200);
      lanzar(error);
      return (data ?? []) as unknown as Alerta[];
    },
    async marcarAlertasVistas() {
      const u = await yo();
      await sb.from('coincidencias').update({ vista: true }).eq('user_id', u.id).eq('vista', false);
    },

    async miAutomotora() {
      const { data, error } = await sb.rpc('mi_automotora');
      lanzar(error);
      return ((data ?? [])[0] as Automotora) ?? null;
    },
    async guardarAutomotora(d) {
      const u = await yo();
      const lugar = ubicacionDe(d.departamento, d.ciudad);
      if (!lugar) throw new Error('Elegí departamento y ciudad.');
      const fila = { ...d, direccion: d.direccion.trim() || null, lat: lugar.lat, lng: lugar.lng };
      const { data: existe } = await sb.from('automotoras').select('id').eq('owner_id', u.id).maybeSingle();
      const { error } = existe
        ? await sb.from('automotoras').update(fila).eq('id', existe.id)
        : await sb.from('automotoras').insert({ ...fila, owner_id: u.id });
      lanzar(error);
    },
    async clientes() {
      const { data, error } = await sb.rpc('mis_clientes');
      lanzar(error);
      return (data ?? []) as Cliente[];
    },
    async contactoCliente(busquedaId) {
      const { data, error } = await sb.rpc('contacto_cliente', { p_busqueda: busquedaId });
      lanzar(error);
      const c = (data ?? [])[0];
      if (!c) throw new Error('Este cliente no autorizó que lo contacten.');
      return c;
    },
    async suscribirse(plan) {
      const r = await funcion<{ url: string }>('mp-subscribe', { plan });
      return r.url;
    },
    async cancelarSuscripcion() {
      await funcion('mp-cancel');
    },
    async pagos() {
      const { data, error } = await sb.from('pagos').select('id, plan, monto, moneda, estado, periodo_hasta, creado').order('creado', { ascending: false });
      lanzar(error);
      return (data ?? []) as RegistroPago[];
    },
  };
}

function escaparLike(s: string): string {
  return s.replace(/[\\%_]/g, (x) => '\\' + x);
}
