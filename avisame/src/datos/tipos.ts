import type { Combustible, Criterios, PlanId, Tipo, Transmision } from '../nucleo';

export type EstadoVehiculo = 'activo' | 'pausado' | 'vendido';
export type Fuente = 'avisame' | 'automotora' | 'mercadolibre' | 'facebook_propio';

export type Vehiculo = {
  id: string;
  owner_id: string | null;
  automotora_id: string | null;
  source: Fuente;
  external_id: string | null;
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
  direccion: string | null;
  lat: number;
  lng: number;
  fotos: string[];
  contacto_nombre: string;
  contacto_whatsapp: string;
  estado: EstadoVehiculo;
  creado: string;
  destacado?: boolean;
  automotora_nombre?: string | null;
};

/** Lo que completa la persona al publicar (sin fotos). */
export type DatosVehiculo = {
  marca: string;
  modelo: string;
  version: string;
  anio: number;
  km: number;
  precio_usd: number;
  transmision: Transmision;
  combustible: Combustible;
  tipo: Tipo;
  traccion_4x4: boolean;
  descripcion: string;
  departamento: string;
  ciudad: string;
  direccion: string;
  contacto_nombre: string;
  contacto_whatsapp: string;
};

export type Usuario = { id: string; email: string };

export type Busqueda = {
  id: string;
  texto: string;
  criterios: Criterios;
  nombre: string;
  whatsapp: string;
  autoriza_contacto: boolean;
  departamento: string;
  ciudad: string;
  lat: number;
  lng: number;
  activa: boolean;
  creado: string;
};

export type NuevaBusqueda = Omit<Busqueda, 'id' | 'activa' | 'creado'>;

export type Alerta = {
  id: string;
  busqueda_id: string;
  distancia_km: number | null;
  vista: boolean;
  creado: string;
  vehiculo: Vehiculo | null;
};

export type Automotora = {
  id: string;
  nombre: string;
  departamento: string;
  ciudad: string;
  direccion: string | null;
  telefono: string;
  lat: number;
  lng: number;
  plan: PlanId;
  plan_vigente: PlanId;
  plan_vence: string | null;
  mp_estado: string | null;
  renovacion_cancelada: boolean;
  tiene_suscripcion: boolean;
};

export type DatosAutomotora = {
  nombre: string;
  departamento: string;
  ciudad: string;
  direccion: string;
  telefono: string;
};

export type Cliente = {
  busqueda_id: string;
  texto: string;
  criterios: Criterios;
  departamento: string;
  ciudad: string;
  lat: number;
  lng: number;
  creado: string;
  vehiculos: { id: string; marca: string; modelo: string; anio: number }[];
  autoriza_contacto: boolean;
};

export type RegistroPago = {
  id: string;
  plan: PlanId;
  monto: number;
  moneda: string;
  estado: string;
  periodo_hasta: string | null;
  creado: string;
};

export type MotivoDenuncia = 'estafa' | 'vendido' | 'datos_falsos' | 'ofensivo' | 'otro';
