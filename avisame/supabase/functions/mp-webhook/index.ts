// mp-webhook: recibe las notificaciones de Mercado Pago.
//
// Es el ÚNICO lugar donde se activa o extiende un plan, y solo cuando Mercado
// Pago confirma un cobro aprobado. Antes de hacer nada verifica la firma
// x-signature con la clave secreta del webhook. Después vuelve a consultar el
// recurso en la API de Mercado Pago (nunca confía en el cuerpo recibido).
import type { SupabaseClient } from 'npm:@supabase/supabase-js@2';
import { admin, enviarPush, env, firmaValida, json, leerReferencia, mp } from '../_shared/servidor.ts';
import { PLANES, esPlanPago, formatoPesos } from '../_shared/nucleo.ts';

type Preapproval = { id: string; status: string; external_reference?: string };
type PagoAutorizado = {
  id: number | string;
  preapproval_id: string;
  status: string;
  transaction_amount: number;
  currency_id: string;
  debit_date?: string;
  payment?: { id: number | string; status: string };
};
type Pago = {
  id: number | string;
  status: string;
  transaction_amount: number;
  currency_id: string;
  external_reference?: string;
  metadata?: { preapproval_id?: string };
  point_of_interaction?: { transaction_data?: { subscription_id?: string } };
};

Deno.serve(async (req) => {
  if (req.method !== 'POST') return new Response('ok');
  const url = new URL(req.url);
  const cuerpo = await req.json().catch(() => ({}));
  const dataId = url.searchParams.get('data.id') ?? url.searchParams.get('id') ?? (cuerpo?.data?.id != null ? String(cuerpo.data.id) : null);
  const tipo = url.searchParams.get('type') ?? url.searchParams.get('topic') ?? cuerpo?.type ?? cuerpo?.topic;

  if (!(await firmaValida(req, dataId, env('MP_WEBHOOK_SECRET')))) {
    console.warn('Firma inválida', { tipo, dataId });
    return json({ error: 'firma inválida' }, 401);
  }
  if (!dataId) return json({ ok: true });

  const db = admin();
  try {
    switch (tipo) {
      case 'subscription_preapproval':
        await suscripcion(db, dataId);
        break;
      case 'subscription_authorized_payment': {
        const ap = await mp<PagoAutorizado>(`/authorized_payments/${dataId}`);
        if (ap.payment?.status === 'approved') {
          await activar(db, ap.preapproval_id, String(ap.payment.id), ap.transaction_amount, ap.currency_id, ap.status);
        }
        break;
      }
      case 'payment': {
        const p = await mp<Pago>(`/v1/payments/${dataId}`);
        const pre = p.metadata?.preapproval_id ?? p.point_of_interaction?.transaction_data?.subscription_id;
        if (p.status === 'approved' && pre) await activar(db, pre, String(p.id), p.transaction_amount, p.currency_id, p.status);
        break;
      }
    }
  } catch (e) {
    // 500 → Mercado Pago reintenta más tarde.
    console.error(e);
    return json({ error: 'reintentar' }, 500);
  }
  return json({ ok: true });
});

/** Cambios de estado de la suscripción (autorizada, pausada, cancelada). */
async function suscripcion(db: SupabaseClient, id: string) {
  const pre = await mp<Preapproval>(`/preapproval/${id}`);
  const ref = leerReferencia(pre.external_reference);
  if (!ref) return;
  const cambios: Record<string, unknown> = { mp_estado: pre.status };
  // Cancelada o pausada: no se renueva, pero el plan sigue hasta plan_vence.
  if (pre.status === 'cancelled' || pre.status === 'paused') cambios.renovacion_cancelada = true;
  await db.from('automotoras').update(cambios).eq('id', ref.automotoraId).eq('mp_preapproval_id', pre.id);
}

/** Cobro aprobado: registra el pago y extiende el plan un mes. Idempotente. */
async function activar(db: SupabaseClient, preapprovalId: string, pagoId: string, monto: number, moneda: string, estado: string) {
  const pre = await mp<Preapproval>(`/preapproval/${preapprovalId}`);
  const ref = leerReferencia(pre.external_reference);
  if (!ref || !esPlanPago(ref.plan)) return;
  const plan = PLANES[ref.plan];
  if (moneda !== 'UYU' || monto + 0.01 < plan.precioUYU) {
    console.error('Monto inesperado', { pagoId, monto, moneda, plan: plan.id });
    return;
  }

  const { data: a } = await db.from('automotoras').select('id, owner_id, plan, plan_vence').eq('id', ref.automotoraId).maybeSingle();
  if (!a) return;

  // Si ya lo registramos, no se extiende dos veces.
  const { data: ya } = await db.from('pagos').select('id').eq('mp_pago_id', pagoId).maybeSingle();
  if (ya) return;

  const ahora = new Date();
  const base = a.plan === plan.id && a.plan_vence && new Date(a.plan_vence) > ahora ? new Date(a.plan_vence) : ahora;
  const vence = new Date(base);
  vence.setMonth(vence.getMonth() + 1);

  const { error: e1 } = await db.from('pagos').insert({
    automotora_id: a.id,
    mp_pago_id: pagoId,
    mp_preapproval_id: preapprovalId,
    plan: plan.id,
    monto,
    moneda,
    estado,
    periodo_hasta: vence.toISOString(),
  });
  if (e1) {
    if (e1.code === '23505') return; // otra notificación del mismo pago llegó primero
    throw e1;
  }
  const { error: e2 } = await db
    .from('automotoras')
    .update({ plan: plan.id, plan_vence: vence.toISOString(), mp_preapproval_id: preapprovalId, mp_estado: 'authorized', mp_plan_pendiente: null })
    .eq('id', a.id);
  if (e2) throw e2;

  const { data: perfil } = await db.from('perfiles').select('push_token').eq('id', a.owner_id).maybeSingle();
  if (perfil?.push_token) {
    await enviarPush([{
      to: perfil.push_token,
      title: `✅ Plan ${plan.nombre} activo`,
      body: `Recibimos tu pago de ${formatoPesos(monto)}. ¡Gracias!`,
      data: { tipo: 'plan' },
    }]);
  }
}
