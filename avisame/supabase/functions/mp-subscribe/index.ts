// mp-subscribe: crea la suscripción mensual (preapproval) en Mercado Pago y
// devuelve el link de pago. El plan NO se activa acá: se activa cuando el
// webhook confirma el cobro.
import { admin, env, error, json, mp, referencia, servir, usuario } from '../_shared/servidor.ts';
import { PLANES, esPlanPago, planVigente } from '../_shared/nucleo.ts';

servir(async (req) => {
  if (req.method !== 'POST') return error('Método no permitido', 405);
  const db = admin();
  const yo = await usuario(req, db);
  if (!yo?.email) return error('Tenés que ingresar', 401);

  const { data: cobros } = await db.rpc('cobros_activos');
  if (cobros !== true) return error('Por ahora Avisame es gratis para automotoras: no hace falta suscribirse.', 409);

  const { plan } = await req.json().catch(() => ({}));
  if (!esPlanPago(plan)) return error('Elegí el plan Pro o Destacado');

  const { data: a } = await db.from('automotoras').select('*').eq('owner_id', yo.id).maybeSingle();
  if (!a) return error('Primero registrá tu automotora', 404);

  // Si hay una suscripción que sigue renovándose, hay que cancelarla antes de cambiar.
  if (a.mp_preapproval_id && a.mp_estado === 'authorized' && !a.renovacion_cancelada) {
    return error('Ya tenés una suscripción activa. Cancelá la renovación para cambiar de plan.', 409);
  }

  const p = PLANES[plan];
  const vigente = planVigente(a.plan, a.plan_vence);
  // Si todavía le quedan días pagos de un plan, la nueva suscripción arranca cuando termina.
  const inicio = vigente !== 'gratis' && a.plan_vence ? new Date(a.plan_vence) : null;

  const pre = await mp<{ id: string; init_point: string; status: string }>('/preapproval', {
    method: 'POST',
    body: {
      reason: `Avisame · Plan ${p.nombre}`,
      external_reference: referencia(a.id, p.id),
      payer_email: yo.email,
      back_url: `${env('APP_URL')}/automotora?pestana=plan`,
      status: 'pending',
      auto_recurring: {
        frequency: 1,
        frequency_type: 'months',
        transaction_amount: p.precioUYU,
        currency_id: 'UYU',
        ...(inicio && inicio > new Date() ? { start_date: inicio.toISOString() } : {}),
      },
    },
  });

  await db
    .from('automotoras')
    .update({ mp_preapproval_id: pre.id, mp_estado: pre.status, mp_plan_pendiente: p.id, renovacion_cancelada: false })
    .eq('id', a.id);

  return json({ url: pre.init_point });
});
