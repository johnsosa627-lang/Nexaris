// mp-cancel: cancela la renovación de la suscripción. El plan sigue hasta el
// final del período ya pagado (plan_vence).
import { admin, error, json, mp, servir, usuario } from '../_shared/servidor.ts';

servir(async (req) => {
  if (req.method !== 'POST') return error('Método no permitido', 405);
  const db = admin();
  const yo = await usuario(req, db);
  if (!yo) return error('Tenés que ingresar', 401);

  const { data: a } = await db.from('automotoras').select('id, mp_preapproval_id, plan_vence').eq('owner_id', yo.id).maybeSingle();
  if (!a?.mp_preapproval_id) return error('No tenés una suscripción para cancelar', 404);

  await mp(`/preapproval/${a.mp_preapproval_id}`, { method: 'PUT', body: { status: 'cancelled' } });
  await db.from('automotoras').update({ renovacion_cancelada: true, mp_estado: 'cancelled', mp_plan_pendiente: null }).eq('id', a.id);
  return json({ ok: true, plan_vence: a.plan_vence });
});
