// Contrato de datos de la app. Hay dos implementaciones:
//  - apiSupabase: la real (Supabase + funciones del servidor).
//  - apiDemo: la VISTA PREVIA, con vehículos de ejemplo en memoria. Se usa
//    cuando no hay credenciales de Supabase o con EXPO_PUBLIC_VISTA_PREVIA=1.
import type { Criterios, PlanId } from '../nucleo';
import type {
  Alerta,
  Automotora,
  Busqueda,
  Cliente,
  DatosAutomotora,
  DatosVehiculo,
  EstadoVehiculo,
  MotivoDenuncia,
  NuevaBusqueda,
  RegistroPago,
  Usuario,
  Vehiculo,
} from './tipos';
import { crearApiDemo } from './apiDemo';
import { crearApiSupabase } from './apiSupabase';

export interface Api {
  vistaPrevia: boolean;

  // Sesión (email + código de 6 dígitos, sin contraseña)
  usuario(): Promise<Usuario | null>;
  escucharSesion(cb: (u: Usuario | null) => void): () => void;
  pedirCodigo(email: string): Promise<void>;
  verificarCodigo(email: string, codigo: string): Promise<void>;
  salir(): Promise<void>;
  borrarCuenta(): Promise<void>;
  guardarPushToken(token: string | null): Promise<void>;

  // Vehículos
  buscarVehiculos(c: Criterios): Promise<Vehiculo[]>;
  vehiculo(id: string): Promise<Vehiculo | null>;
  misVehiculos(): Promise<Vehiculo[]>;
  /** fotos: URLs ya subidas o URIs locales (se suben). Devuelve el id. */
  guardarVehiculo(datos: DatosVehiculo, fotos: string[], opciones: { id?: string; automotoraId?: string }): Promise<string>;
  cambiarEstado(id: string, estado: EstadoVehiculo): Promise<void>;
  borrarVehiculo(id: string): Promise<void>;
  denunciar(vehiculoId: string, motivo: MotivoDenuncia, detalle: string): Promise<void>;

  // Búsquedas guardadas y alertas
  guardarBusqueda(b: NuevaBusqueda): Promise<void>;
  misBusquedas(): Promise<Busqueda[]>;
  borrarBusqueda(id: string): Promise<void>;
  alertas(): Promise<Alerta[]>;
  marcarAlertasVistas(): Promise<void>;

  // Automotoras
  miAutomotora(): Promise<Automotora | null>;
  guardarAutomotora(datos: DatosAutomotora): Promise<void>;
  clientes(): Promise<Cliente[]>;
  contactoCliente(busquedaId: string): Promise<{ nombre: string; whatsapp: string }>;
  /** Devuelve el link de pago de Mercado Pago. */
  suscribirse(plan: Exclude<PlanId, 'gratis'>): Promise<string>;
  cancelarSuscripcion(): Promise<void>;
  pagos(): Promise<RegistroPago[]>;
}

const url = process.env.EXPO_PUBLIC_SUPABASE_URL;
const clave = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY;
const forzarVistaPrevia = process.env.EXPO_PUBLIC_VISTA_PREVIA === '1';

export const api: Api = !forzarVistaPrevia && url && clave ? crearApiSupabase(url, clave) : crearApiDemo();

/** Mensaje legible de cualquier error. */
export function mensajeError(e: unknown): string {
  if (e instanceof Error) return e.message;
  if (typeof e === 'object' && e && 'message' in e) return String((e as { message: unknown }).message);
  return 'Algo salió mal. Probá de nuevo.';
}
