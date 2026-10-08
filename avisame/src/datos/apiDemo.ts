// VISTA PREVIA: todo pasa en memoria, con vehículos de ejemplo. No se envía
// nada a ningún servidor, no se cobra y no hay notificaciones reales.
import {
  evaluar,
  interpretar,
  mensajeAlerta,
  nombreLugar,
  distanciaA,
  ubicacionDe,
  planVigente,
  PLANES,
  type Criterios,
  type VehiculoBase,
} from '../nucleo';
import type { Api } from './api';
import { busquedasEjemplo, vehiculosEjemplo } from './ejemplos';
import type { Alerta, Automotora, Busqueda, RegistroPago, Usuario, Vehiculo } from './tipos';

export const CODIGO_VISTA_PREVIA = '123456';

type AvisoDemo = { titulo: string; cuerpo: string; vehiculoId?: string };
const oyentesAvisos = new Set<(a: AvisoDemo) => void>();

/** La vista previa muestra los "avisos al celular" como un cartel dentro de la app. */
export function escucharAvisosDemo(cb: (a: AvisoDemo) => void): () => void {
  oyentesAvisos.add(cb);
  return () => oyentesAvisos.delete(cb);
}
function avisar(a: AvisoDemo) {
  oyentesAvisos.forEach((cb) => cb(a));
}

const espera = (ms = 250) => new Promise((r) => setTimeout(r, ms));

export function crearApiDemo(): Api {
  let usuario: Usuario | null = null;
  const oyentes = new Set<(u: Usuario | null) => void>();
  let vehiculos: Vehiculo[] = vehiculosEjemplo();
  let busquedas: (Busqueda & { user_id: string })[] = busquedasEjemplo().map((b) => ({ ...b, criterios: interpretar(b.texto) }));
  let alertas: (Omit<Alerta, 'vehiculo'> & { user_id: string; vehiculo_id: string })[] = [];
  let automotora: (Automotora & { owner_id: string }) | null = null;
  let pagos: RegistroPago[] = [];
  let contador = 1000;
  const nuevoId = (p: string) => `${p}-${++contador}`;

  const yo = () => {
    if (!usuario) throw new Error('Tenés que ingresar con tu email.');
    return usuario;
  };
  const cambiarSesion = (u: Usuario | null) => {
    usuario = u;
    oyentes.forEach((cb) => cb(u));
  };
  const conDestacado = (v: Vehiculo): Vehiculo =>
    automotora && v.automotora_id === automotora.id ? { ...v, destacado: PLANES[automotora.plan_vigente].destacado } : v;

  /** Igual que la función `match` del servidor, pero en memoria. */
  function cruzarVehiculo(v: Vehiculo) {
    if (v.estado !== 'activo') return;
    for (const b of busquedas) {
      if (b.user_id === v.owner_id || !b.activa) continue;
      if (alertas.some((a) => a.busqueda_id === b.id && a.vehiculo_id === v.id)) continue;
      if (evaluar(v, b.criterios).estado !== 'coincide') continue;
      const distancia = distanciaA(b, v);
      alertas.unshift({ id: nuevoId('al'), busqueda_id: b.id, vehiculo_id: v.id, user_id: b.user_id, distancia_km: distancia, vista: false, creado: new Date().toISOString() });
      if (usuario && b.user_id === usuario.id) {
        const m = mensajeAlerta(v, distancia, nombreLugar(b.departamento, b.ciudad));
        avisar({ titulo: m.titulo, cuerpo: m.cuerpo, vehiculoId: v.id });
      }
    }
  }

  /** Para mostrar el "Avisame": unos segundos después aparece un vehículo de ejemplo que coincide. */
  function simularPublicacion(b: Busqueda & { user_id: string }) {
    const c = b.criterios;
    if (!c.marca && !c.tipo) return;
    const base = vehiculosEjemplo().find((v) => (!c.marca || v.marca === c.marca) && (!c.modelo || v.modelo === c.modelo) && (!c.tipo || v.tipo === c.tipo));
    const anio = c.anioMax ?? Math.max(c.anioMin ?? 0, base?.anio ?? 2021);
    const lejos = ubicacionDe('Salto', 'Salto')!;
    const v: Vehiculo = {
      ...(base ?? vehiculosEjemplo()[0]),
      id: nuevoId('ej'),
      owner_id: 'vendedor-simulado',
      automotora_id: null,
      source: 'avisame',
      marca: c.marca ?? base?.marca ?? 'Toyota',
      modelo: c.modelo ?? base?.modelo ?? 'Corolla',
      tipo: c.tipo ?? base?.tipo ?? 'sedan',
      anio,
      km: Math.min(c.kmMax ?? 40000, 40000),
      precio_usd: Math.min(c.precioMax ?? 99999, Math.max(c.precioMin ?? 0, base?.precio_usd ?? 15000)),
      transmision: c.transmision ?? base?.transmision ?? 'automatica',
      combustible: c.combustible ?? base?.combustible ?? 'nafta',
      traccion_4x4: c.traccion4x4 ?? base?.traccion_4x4 ?? false,
      departamento: lejos.departamento,
      ciudad: lejos.ciudad,
      lat: lejos.lat,
      lng: lejos.lng,
      contacto_nombre: 'Vendedor de ejemplo',
      contacto_whatsapp: '099000111',
      estado: 'activo',
      creado: new Date().toISOString(),
      destacado: false,
      automotora_nombre: null,
      descripcion: 'Publicación simulada para mostrar cómo funciona "Avisame cuando aparezca".',
    };
    setTimeout(() => {
      vehiculos = [v, ...vehiculos];
      cruzarVehiculo(v);
    }, 7000);
  }

  function misClientes() {
    if (!automotora) return [];
    const inventario = vehiculos.filter((v) => v.automotora_id === automotora!.id && v.estado === 'activo');
    return busquedas
      .filter((b) => b.activa && (!usuario || b.user_id !== usuario.id))
      .map((b) => ({ b, coinciden: inventario.filter((v) => evaluar(v as VehiculoBase, b.criterios).estado === 'coincide') }))
      .filter((x) => x.coinciden.length > 0)
      .map(({ b, coinciden }) => ({
        busqueda_id: b.id,
        texto: b.texto,
        criterios: b.criterios,
        departamento: b.departamento,
        ciudad: b.ciudad,
        lat: b.lat,
        lng: b.lng,
        creado: b.creado,
        vehiculos: coinciden.map((v) => ({ id: v.id, marca: v.marca, modelo: v.modelo, anio: v.anio })),
        autoriza_contacto: b.autoriza_contacto,
      }));
  }

  return {
    vistaPrevia: true,

    async usuario() {
      return usuario;
    },
    escucharSesion(cb) {
      oyentes.add(cb);
      return () => oyentes.delete(cb);
    },
    async pedirCodigo(email) {
      await espera();
      if (!/^\S+@\S+\.\S+$/.test(email.trim())) throw new Error('Escribí un email válido.');
    },
    async verificarCodigo(email, codigo) {
      await espera();
      if (codigo.trim() !== CODIGO_VISTA_PREVIA) throw new Error(`En la vista previa el código es ${CODIGO_VISTA_PREVIA}.`);
      cambiarSesion({ id: 'usuario-vista-previa', email: email.trim().toLowerCase() });
    },
    async salir() {
      cambiarSesion(null);
    },
    async borrarCuenta() {
      const u = yo();
      vehiculos = vehiculos.filter((v) => v.owner_id !== u.id);
      busquedas = busquedas.filter((b) => b.user_id !== u.id);
      alertas = alertas.filter((a) => a.user_id !== u.id);
      if (automotora?.owner_id === u.id) {
        vehiculos = vehiculos.filter((v) => v.automotora_id !== automotora!.id);
        automotora = null;
        pagos = [];
      }
      cambiarSesion(null);
    },
    async guardarPushToken() {},

    async buscarVehiculos() {
      await espera(150);
      return vehiculos.filter((v) => v.estado === 'activo').map(conDestacado);
    },
    async vehiculo(id) {
      const v = vehiculos.find((x) => x.id === id);
      if (!v) return null;
      if (v.estado !== 'activo' && v.owner_id !== usuario?.id) return null;
      return conDestacado(v);
    },
    async misVehiculos() {
      const u = yo();
      return vehiculos.filter((v) => v.owner_id === u.id).map(conDestacado);
    },
    async guardarVehiculo(datos, fotos, { id, automotoraId }) {
      const u = yo();
      await espera(600);
      const lugar = ubicacionDe(datos.departamento, datos.ciudad)!;
      const deAutomotora = automotoraId && automotora?.id === automotoraId ? automotora : null;
      const comun = {
        ...datos,
        version: datos.version.trim() || null,
        descripcion: datos.descripcion.trim() || null,
        direccion: datos.direccion.trim() || deAutomotora?.direccion || null,
        lat: lugar.lat,
        lng: lugar.lng,
        fotos,
        contacto_nombre: deAutomotora?.nombre ?? datos.contacto_nombre,
        contacto_whatsapp: deAutomotora?.telefono ?? datos.contacto_whatsapp,
      };
      if (id) {
        vehiculos = vehiculos.map((v) => (v.id === id && v.owner_id === u.id ? { ...v, ...comun } : v));
        const v = vehiculos.find((x) => x.id === id);
        if (v) cruzarVehiculo(v);
        return id;
      }
      const v: Vehiculo = {
        ...comun,
        id: nuevoId('v'),
        owner_id: u.id,
        automotora_id: deAutomotora?.id ?? null,
        source: deAutomotora ? 'automotora' : 'avisame',
        external_id: null,
        external_url: null,
        estado: 'activo',
        creado: new Date().toISOString(),
        automotora_nombre: deAutomotora?.nombre ?? null,
      };
      vehiculos = [v, ...vehiculos];
      cruzarVehiculo(v);
      return v.id;
    },
    async cambiarEstado(id, estado) {
      const u = yo();
      vehiculos = vehiculos.map((v) => (v.id === id && v.owner_id === u.id ? { ...v, estado } : v));
      const v = vehiculos.find((x) => x.id === id);
      if (v) cruzarVehiculo(v);
    },
    async borrarVehiculo(id) {
      const u = yo();
      vehiculos = vehiculos.filter((v) => !(v.id === id && v.owner_id === u.id));
    },
    async denunciar() {
      await espera();
    },

    async guardarBusqueda(nueva) {
      const u = yo();
      await espera();
      const b = { ...nueva, id: nuevoId('b'), user_id: u.id, activa: true, creado: new Date().toISOString() };
      busquedas = [b, ...busquedas];
      // Lo que ya está publicado queda registrado, pero no se avisa.
      for (const v of vehiculos) {
        if (v.estado === 'activo' && v.owner_id !== u.id && evaluar(v, b.criterios).estado === 'coincide') {
          alertas.push({ id: nuevoId('al'), busqueda_id: b.id, vehiculo_id: v.id, user_id: u.id, distancia_km: distanciaA(b, v), vista: true, creado: new Date().toISOString() });
        }
      }
      simularPublicacion(b);
    },
    async misBusquedas() {
      const u = yo();
      return busquedas.filter((b) => b.user_id === u.id);
    },
    async borrarBusqueda(id) {
      const u = yo();
      busquedas = busquedas.filter((b) => !(b.id === id && b.user_id === u.id));
      alertas = alertas.filter((a) => a.busqueda_id !== id);
    },
    async alertas() {
      const u = yo();
      return alertas
        .filter((a) => a.user_id === u.id)
        .map((a) => {
          const v = vehiculos.find((x) => x.id === a.vehiculo_id);
          return { ...a, vehiculo: v && v.estado === 'activo' ? conDestacado(v) : null };
        });
    },
    async marcarAlertasVistas() {
      const u = yo();
      alertas = alertas.map((a) => (a.user_id === u.id ? { ...a, vista: true } : a));
    },

    async miAutomotora() {
      const u = yo();
      if (!automotora || automotora.owner_id !== u.id) return null;
      automotora.plan_vigente = planVigente(automotora.plan, automotora.plan_vence);
      return { ...automotora };
    },
    async guardarAutomotora(d) {
      const u = yo();
      const lugar = ubicacionDe(d.departamento, d.ciudad);
      if (!lugar) throw new Error('Elegí departamento y ciudad.');
      const datos = { ...d, direccion: d.direccion.trim() || null, lat: lugar.lat, lng: lugar.lng };
      if (automotora) automotora = { ...automotora, ...datos };
      else {
        automotora = {
          ...datos, id: nuevoId('auto'), owner_id: u.id, plan: 'gratis', plan_vigente: 'gratis', plan_vence: null,
          mp_estado: null, renovacion_cancelada: false, tiene_suscripcion: false, cobros_activos: false,
        };
        // Para que el panel tenga algo que mostrar, la automotora nueva arranca
        // con dos vehículos de ejemplo en su inventario.
        const ej = vehiculosEjemplo();
        for (const base of [ej[0], ej[19]]) {
          vehiculos.unshift({
            ...base, id: nuevoId('v'), owner_id: u.id, automotora_id: automotora.id, source: 'automotora',
            contacto_nombre: automotora.nombre, contacto_whatsapp: automotora.telefono, automotora_nombre: automotora.nombre,
            departamento: lugar.departamento, ciudad: lugar.ciudad, lat: lugar.lat, lng: lugar.lng, destacado: false,
          });
        }
      }
      const a = automotora;
      vehiculos = vehiculos.map((v) => (v.automotora_id === a.id ? { ...v, contacto_nombre: a.nombre, contacto_whatsapp: a.telefono, automotora_nombre: a.nombre } : v));
    },
    async clientes() {
      await espera(150);
      return misClientes();
    },
    async contactoCliente(busquedaId) {
      await espera();
      if (!automotora || (automotora.cobros_activos && !PLANES[planVigente(automotora.plan, automotora.plan_vence)].verContactos)) {
        throw new Error('Necesitás el plan Pro o Destacado al día para ver el contacto.');
      }
      const c = misClientes().find((x) => x.busqueda_id === busquedaId);
      const b = busquedas.find((x) => x.id === busquedaId);
      if (!c || !b || !b.autoriza_contacto) throw new Error('Este cliente no autorizó que lo contacten.');
      return { nombre: b.nombre, whatsapp: b.whatsapp };
    },
    async suscribirse(plan) {
      // En la app real esto abre Mercado Pago y el plan se activa cuando el
      // webhook confirma el cobro. En la vista previa se simula esa confirmación.
      if (!automotora) throw new Error('Primero registrá tu automotora.');
      if (!automotora.cobros_activos) throw new Error('Por ahora Avisame es gratis para automotoras: no hace falta suscribirse.');
      await espera(500);
      const vence = new Date();
      vence.setMonth(vence.getMonth() + 1);
      automotora = { ...automotora, plan, plan_vigente: plan, plan_vence: vence.toISOString(), mp_estado: 'authorized', renovacion_cancelada: false, tiene_suscripcion: true };
      pagos = [{ id: nuevoId('pago'), plan, monto: PLANES[plan].precioUYU, moneda: 'UYU', estado: 'approved (simulado)', periodo_hasta: vence.toISOString(), creado: new Date().toISOString() }, ...pagos];
      return '';
    },
    async cancelarSuscripcion() {
      if (automotora) automotora = { ...automotora, renovacion_cancelada: true, mp_estado: 'cancelled' };
    },
    async pagos() {
      return pagos;
    },
  };
}

export type { AvisoDemo, Criterios };
