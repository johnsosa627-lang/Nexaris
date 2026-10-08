// Utilidades comunes de las funciones del servidor (Deno).
import { createClient, type SupabaseClient, type User } from 'npm:@supabase/supabase-js@2';

export const cors = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
};

export function json(cuerpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(cuerpo), { status, headers: { ...cors, 'Content-Type': 'application/json' } });
}

export function error(mensaje: string, status = 400): Response {
  return json({ error: mensaje }, status);
}

export function env(nombre: string): string {
  const v = Deno.env.get(nombre);
  if (!v) throw new Error(`Falta la variable de entorno ${nombre}`);
  return v;
}

/** Cliente con permisos de servidor (salta RLS). Nunca sale de acá. */
export function admin(): SupabaseClient {
  return createClient(env('SUPABASE_URL'), env('SUPABASE_SERVICE_ROLE_KEY'), {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

/** La persona que llama, a partir de su token. */
export async function usuario(req: Request, db: SupabaseClient): Promise<User | null> {
  const token = req.headers.get('Authorization')?.replace(/^Bearer\s+/i, '');
  if (!token) return null;
  const { data, error } = await db.auth.getUser(token);
  if (error || !data.user) return null;
  return data.user;
}

/** Envuelve un manejador con CORS y manejo de errores. */
export function servir(manejador: (req: Request) => Promise<Response>): void {
  Deno.serve(async (req) => {
    if (req.method === 'OPTIONS') return new Response('ok', { headers: cors });
    try {
      return await manejador(req);
    } catch (e) {
      console.error(e);
      return error('Algo salió mal. Probá de nuevo en un rato.', 500);
    }
  });
}

// ───────────────────────────── Notificaciones push (Expo) ────────────────────

export type Push = { to: string; title: string; body: string; data?: Record<string, unknown> };

export async function enviarPush(mensajes: Push[]): Promise<void> {
  const validos = mensajes.filter((m) => /^Expo(nent)?PushToken\[.+\]$/.test(m.to));
  const headers: Record<string, string> = { 'Content-Type': 'application/json', Accept: 'application/json' };
  const token = Deno.env.get('EXPO_ACCESS_TOKEN');
  if (token) headers.Authorization = `Bearer ${token}`;
  for (let i = 0; i < validos.length; i += 100) {
    const lote = validos.slice(i, i + 100).map((m) => ({ ...m, sound: 'default', channelId: 'avisos', priority: 'high' }));
    const r = await fetch('https://exp.host/--/api/v2/push/send', { method: 'POST', headers, body: JSON.stringify(lote) });
    if (!r.ok) console.error('Expo push', r.status, await r.text());
  }
}

// ───────────────────────────── Mercado Pago ──────────────────────────────────

const MP_API = 'https://api.mercadopago.com';

export async function mp<T = Record<string, unknown>>(ruta: string, opciones: { method?: string; body?: unknown } = {}): Promise<T> {
  const r = await fetch(MP_API + ruta, {
    method: opciones.method ?? 'GET',
    headers: { Authorization: `Bearer ${env('MP_ACCESS_TOKEN')}`, 'Content-Type': 'application/json' },
    body: opciones.body ? JSON.stringify(opciones.body) : undefined,
  });
  const texto = await r.text();
  if (!r.ok) throw new Error(`Mercado Pago ${ruta} → ${r.status}: ${texto}`);
  return JSON.parse(texto) as T;
}

/** external_reference de las suscripciones: "avisame:<automotora>:<plan>". */
export function referencia(automotoraId: string, plan: string): string {
  return `avisame:${automotoraId}:${plan}`;
}

export function leerReferencia(ref: unknown): { automotoraId: string; plan: string } | null {
  if (typeof ref !== 'string') return null;
  const m = /^avisame:([0-9a-f-]{36}):(pro|destacado)$/.exec(ref);
  return m ? { automotoraId: m[1], plan: m[2] } : null;
}

/**
 * Verifica la firma x-signature de Mercado Pago.
 * Plantilla: "id:<data.id>;request-id:<x-request-id>;ts:<ts>;" firmada con HMAC-SHA256.
 */
export async function firmaValida(req: Request, dataId: string | null, secreto: string): Promise<boolean> {
  const firma = req.headers.get('x-signature');
  const requestId = req.headers.get('x-request-id');
  if (!firma) return false;
  const partes = Object.fromEntries(
    firma.split(',').map((p) => {
      const [k, ...v] = p.trim().split('=');
      return [k, v.join('=')];
    }),
  );
  const ts = partes.ts;
  const v1 = partes.v1;
  if (!ts || !v1) return false;
  let plantilla = '';
  if (dataId) plantilla += `id:${/^[a-z0-9]+$/i.test(dataId) ? dataId.toLowerCase() : dataId};`;
  if (requestId) plantilla += `request-id:${requestId};`;
  plantilla += `ts:${ts};`;
  const clave = await crypto.subtle.importKey('raw', new TextEncoder().encode(secreto), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const sig = new Uint8Array(await crypto.subtle.sign('HMAC', clave, new TextEncoder().encode(plantilla)));
  const hex = Array.from(sig, (b) => b.toString(16).padStart(2, '0')).join('');
  return iguales(hex, v1.toLowerCase());
}

/** Comparación en tiempo constante. */
function iguales(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let r = 0;
  for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}
