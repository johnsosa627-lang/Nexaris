// delete-account: borra la cuenta y todo lo asociado (publicaciones, fotos,
// búsquedas, alertas, automotora y pagos) y cancela la suscripción.
import type { SupabaseClient } from 'npm:@supabase/supabase-js@2';
import { admin, error, json, mp, servir, usuario } from '../_shared/servidor.ts';

servir(async (req) => {
  if (req.method !== 'POST') return error('Método no permitido', 405);
  const db = admin();
  const yo = await usuario(req, db);
  if (!yo) return error('Tenés que ingresar', 401);

  // 1) Cancelar la suscripción para que no se le cobre nunca más.
  const { data: a } = await db.from('automotoras').select('mp_preapproval_id, mp_estado').eq('owner_id', yo.id).maybeSingle();
  if (a?.mp_preapproval_id && a.mp_estado !== 'cancelled') {
    try {
      await mp(`/preapproval/${a.mp_preapproval_id}`, { method: 'PUT', body: { status: 'cancelled' } });
    } catch (e) {
      console.error(e);
      return error('No pudimos cancelar tu suscripción en Mercado Pago. Probá de nuevo en un rato.', 502);
    }
  }

  // 2) Borrar las fotos de su carpeta.
  await borrarCarpeta(db, yo.id);

  // 3) Borrar el usuario: el resto se borra en cascada en la base.
  const { error: e } = await db.auth.admin.deleteUser(yo.id);
  if (e) throw e;
  return json({ ok: true });
});

async function borrarCarpeta(db: SupabaseClient, carpeta: string): Promise<void> {
  const fotos = db.storage.from('fotos');
  for (;;) {
    const { data, error: e } = await fotos.list(carpeta, { limit: 1000 });
    if (e) throw e;
    if (!data || data.length === 0) return;
    const archivos = data.filter((x) => x.id).map((x) => `${carpeta}/${x.name}`);
    for (const sub of data.filter((x) => !x.id)) await borrarCarpeta(db, `${carpeta}/${sub.name}`);
    if (archivos.length) {
      const { error: e2 } = await fotos.remove(archivos);
      if (e2) throw e2;
    }
    if (data.length < 1000) return;
  }
}
