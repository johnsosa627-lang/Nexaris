// Prueba de la verificación de firma del webhook de Mercado Pago.
// Se corre con Deno: deno test pruebas/firma.test.ts
import { assertEquals } from 'jsr:@std/assert@1';
import { firmaValida, leerReferencia, referencia } from '../supabase/functions/_shared/servidor.ts';

async function firmar(secreto: string, plantilla: string): Promise<string> {
  const clave = await crypto.subtle.importKey('raw', new TextEncoder().encode(secreto), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const sig = new Uint8Array(await crypto.subtle.sign('HMAC', clave, new TextEncoder().encode(plantilla)));
  return Array.from(sig, (b) => b.toString(16).padStart(2, '0')).join('');
}

function pedido(firma: string | null, requestId = 'req-123'): Request {
  const headers = new Headers({ 'x-request-id': requestId });
  if (firma) headers.set('x-signature', firma);
  return new Request('https://x/functions/v1/mp-webhook?data.id=ABC123&type=payment', { method: 'POST', headers });
}

Deno.test('acepta una firma correcta (id en minúsculas)', async () => {
  const v1 = await firmar('secreto', 'id:abc123;request-id:req-123;ts:1700000000;');
  assertEquals(await firmaValida(pedido(`ts=1700000000,v1=${v1}`), 'ABC123', 'secreto'), true);
});

Deno.test('rechaza firma con otro secreto, sin firma o alterada', async () => {
  const v1 = await firmar('otro', 'id:abc123;request-id:req-123;ts:1700000000;');
  assertEquals(await firmaValida(pedido(`ts=1700000000,v1=${v1}`), 'ABC123', 'secreto'), false);
  assertEquals(await firmaValida(pedido(null), 'ABC123', 'secreto'), false);
  const bien = await firmar('secreto', 'id:abc123;request-id:req-123;ts:1700000000;');
  assertEquals(await firmaValida(pedido(`ts=1700000001,v1=${bien}`), 'ABC123', 'secreto'), false);
  assertEquals(await firmaValida(pedido(`ts=1700000000,v1=${bien}`), 'XYZ', 'secreto'), false);
});

Deno.test('referencia de la suscripción', () => {
  const id = '0f8fad5b-d9cb-469f-a165-70867728950e';
  assertEquals(leerReferencia(referencia(id, 'pro')), { automotoraId: id, plan: 'pro' });
  assertEquals(leerReferencia(`avisame:${id}:gratis`), null);
  assertEquals(leerReferencia('cualquier cosa'), null);
});
