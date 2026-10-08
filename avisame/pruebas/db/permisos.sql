-- Prueba de la base y de los permisos (RLS + permisos por columna).
-- Cada bloque dice qué se espera. Si algo no se cumple, se corta con error.
\set ON_ERROR_STOP 1
\set QUIET 1
-- Solo se muestran los avisos (ok · …); los resultados de las consultas se descartan.
\o /dev/null

-- Personas de prueba
\set ana     '''aaaaaaaa-0000-0000-0000-000000000001'''
\set beto    '''bbbbbbbb-0000-0000-0000-000000000002'''
\set carla   '''cccccccc-0000-0000-0000-000000000003'''
\set diego   '''dddddddd-0000-0000-0000-000000000004'''

insert into auth.users (id, email) values
  (:ana, 'ana@ejemplo.uy'), (:beto, 'automotora@ejemplo.uy'), (:carla, 'carla@ejemplo.uy'), (:diego, 'diego@ejemplo.uy');

create function pg_temp.esperar(cond boolean, mensaje text) returns void language plpgsql as $$
begin
  if not cond then raise exception 'FALLÓ: %', mensaje; end if;
  raise notice 'ok · %', mensaje;
end $$;
grant execute on function pg_temp.esperar(boolean, text) to anon, authenticated;

select pg_temp.esperar((select count(*) from public.perfiles) = 4, 'se crea un perfil por usuario');

-- ═══ Ana, particular ═══
set role authenticated;
select set_config('request.jwt.claims', json_build_object('sub', :ana)::text, false);

insert into public.vehiculos (marca, modelo, anio, km, precio_usd, transmision, combustible, tipo, departamento, ciudad, lat, lng, fotos, contacto_nombre, contacto_whatsapp)
values ('Hyundai', 'Creta', 2023, 40000, 17500, 'automatica', 'nafta', 'suv', 'Canelones', 'Atlántida', -34.77, -55.76, '{https://x/1.jpg}', 'Ana', '099123456');
select pg_temp.esperar((select owner_id from public.vehiculos where marca = 'Hyundai') = :ana, 'Ana publica y queda como dueña');

do $$ begin
  insert into public.vehiculos (owner_id, marca, modelo, anio, km, precio_usd, transmision, combustible, tipo, departamento, ciudad, lat, lng, fotos, contacto_nombre, contacto_whatsapp)
  values ('bbbbbbbb-0000-0000-0000-000000000002', 'Fiat', 'Uno', 2010, 1, 1000, 'manual', 'nafta', 'hatch', 'Salto', 'Salto', -31.4, -57.9, '{x}', 'X', '099123456');
  raise exception 'FALLÓ: publicó a nombre de otro';
exception when insufficient_privilege then raise notice 'ok · no puede publicar a nombre de otro';
end $$;

do $$ begin
  insert into public.vehiculos (source, external_id, marca, modelo, anio, km, precio_usd, transmision, combustible, tipo, departamento, ciudad, lat, lng, fotos, contacto_nombre, contacto_whatsapp)
  values ('mercadolibre', 'MLU1', 'Fiat', 'Uno', 2010, 1, 1000, 'manual', 'nafta', 'hatch', 'Salto', 'Salto', -31.4, -57.9, '{x}', 'X', '099123456');
  raise exception 'FALLÓ: cargó un vehículo como si viniera de Mercado Libre';
exception when insufficient_privilege then raise notice 'ok · no puede inventar la fuente';
end $$;

do $$ begin
  insert into public.vehiculos (marca, modelo, anio, km, precio_usd, transmision, combustible, tipo, departamento, ciudad, lat, lng, fotos, contacto_nombre, contacto_whatsapp)
  values ('Fiat', 'Uno', 2010, 1, 1000, 'manual', 'nafta', 'hatch', 'Salto', 'Salto', -31.4, -57.9, '{}', 'X', '099123456');
  raise exception 'FALLÓ: publicó sin fotos';
exception when check_violation then raise notice 'ok · hace falta al menos una foto';
end $$;

do $$ begin
  insert into public.vehiculos (source, marca, modelo, anio, km, precio_usd, transmision, combustible, tipo, departamento, ciudad, lat, lng, fotos, contacto_nombre, contacto_whatsapp)
  values ('automotora', 'Fiat', 'Uno', 2010, 1, 1000, 'manual', 'nafta', 'hatch', 'Salto', 'Salto', -31.4, -57.9, '{x}', 'X', '099123456');
  raise exception 'FALLÓ: se hizo pasar por automotora';
exception when check_violation then raise notice 'ok · un particular no puede figurar como automotora';
end $$;

-- Fotos: solo en su carpeta
insert into storage.objects (bucket_id, name) values ('fotos', 'aaaaaaaa-0000-0000-0000-000000000001/v1/1.jpg');
select pg_temp.esperar(true, 'sube fotos a su carpeta');
do $$ begin
  insert into storage.objects (bucket_id, name) values ('fotos', 'bbbbbbbb-0000-0000-0000-000000000002/v1/1.jpg');
  raise exception 'FALLÓ: subió a la carpeta de otro';
exception when insufficient_privilege then raise notice 'ok · no puede subir a la carpeta de otro';
end $$;

-- ═══ Beto, automotora ═══
select set_config('request.jwt.claims', json_build_object('sub', :beto)::text, false);

insert into public.automotoras (nombre, departamento, ciudad, direccion, telefono, lat, lng)
values ('Autos del Este', 'Maldonado', 'Maldonado', 'Av. Roosevelt 1234', '42223344', -34.9, -54.95);

do $$ begin
  update public.automotoras set plan = 'destacado', plan_vence = now() + interval '1 year';
  raise exception 'FALLÓ: la automotora se cambió el plan';
exception when insufficient_privilege then raise notice 'ok · la automotora no puede cambiarse el plan';
end $$;

do $$ begin
  insert into public.automotoras (owner_id, nombre, departamento, ciudad, telefono, lat, lng, plan)
  values ('bbbbbbbb-0000-0000-0000-000000000002', 'Trampa', 'Salto', 'Salto', '099123456', -31.4, -57.9, 'pro');
  raise exception 'FALLÓ: creó una automotora con plan pago';
exception when insufficient_privilege then raise notice 'ok · no puede crear una automotora con plan pago';
end $$;

select pg_temp.esperar((select plan_vigente from public.mi_automotora()) = 'gratis', 'arranca con plan Gratis');

insert into public.vehiculos (automotora_id, marca, modelo, anio, km, precio_usd, transmision, combustible, tipo, departamento, ciudad, lat, lng, fotos, contacto_nombre, contacto_whatsapp)
select id, 'Toyota', 'Hilux', 2021, 60000, 38000, 'manual', 'diesel', 'pickup', '', '', 0 - 34.9, 0 - 54.95, '{https://x/2.jpg}', '-', '-' from public.automotoras;
select pg_temp.esperar(
  (select contacto_nombre = 'Autos del Este' and contacto_whatsapp = '42223344' and source = 'automotora'
          and ciudad = 'Maldonado' and direccion = 'Av. Roosevelt 1234'
   from public.vehiculos where modelo = 'Hilux'),
  'los datos de la automotora se completan solos en el vehículo');

update public.automotoras set nombre = 'Autos del Este SRL';
select pg_temp.esperar((select contacto_nombre from public.vehiculos where modelo = 'Hilux') = 'Autos del Este SRL', 'si cambia el nombre, se actualiza el inventario');

select pg_temp.esperar((select count(*) from public.vehiculos where modelo = 'Creta' and owner_id = auth.uid()) = 0, 'no ve como propio el vehículo de Ana');
update public.vehiculos set precio_usd = 1 where modelo = 'Creta';
select pg_temp.esperar((select precio_usd from public.vehiculos where modelo = 'Creta') = 17500, 'no puede editar el vehículo de Ana');
delete from public.vehiculos where modelo = 'Creta';
select pg_temp.esperar((select count(*) from public.vehiculos where modelo = 'Creta') = 1, 'no puede borrar el vehículo de Ana');

-- ═══ Ana intenta cargar en la automotora de Beto ═══
select set_config('request.jwt.claims', json_build_object('sub', :ana)::text, false);
do $$ begin
  insert into public.vehiculos (automotora_id, marca, modelo, anio, km, precio_usd, transmision, combustible, tipo, departamento, ciudad, lat, lng, fotos, contacto_nombre, contacto_whatsapp)
  select id, 'Fiat', 'Uno', 2010, 1, 1000, 'manual', 'nafta', 'hatch', 'Salto', 'Salto', -31.4, -57.9, '{x}', 'X', '099123456' from public.automotoras;
  raise exception 'FALLÓ: cargó en una automotora ajena';
exception when insufficient_privilege then raise notice 'ok · no puede cargar en una automotora ajena';
end $$;
do $$ begin
  update public.vehiculos set source = 'mercadolibre' where modelo = 'Creta';
  raise exception 'FALLÓ: cambió la fuente';
exception when insufficient_privilege then raise notice 'ok · no puede cambiar la fuente de su publicación';
end $$;

-- ═══ Carla y Diego guardan búsquedas ═══
select set_config('request.jwt.claims', json_build_object('sub', :carla)::text, false);
insert into public.busquedas (texto, criterios, nombre, whatsapp, autoriza_contacto, departamento, ciudad, lat, lng)
values ('hilux diesel', '{"marca":"Toyota","modelo":"Hilux"}', 'Carla', '098111222', true, 'Rocha', 'Rocha', -34.48, -54.33);

select set_config('request.jwt.claims', json_build_object('sub', :diego)::text, false);
insert into public.busquedas (texto, criterios, nombre, whatsapp, autoriza_contacto, departamento, ciudad, lat, lng)
values ('hilux', '{"marca":"Toyota","modelo":"Hilux"}', 'Diego', '097333444', false, 'Salto', 'Salto', -31.38, -57.96);
select pg_temp.esperar((select count(*) from public.busquedas) = 1, 'cada uno ve solo sus búsquedas');

-- El servidor (función match) registra las coincidencias
reset role;
insert into public.coincidencias (busqueda_id, vehiculo_id, user_id, distancia_km)
select b.id, v.id, b.user_id, 100 from public.busquedas b, public.vehiculos v where v.modelo = 'Hilux';
set role authenticated;

select set_config('request.jwt.claims', json_build_object('sub', :carla)::text, false);
select pg_temp.esperar((select count(*) from public.coincidencias) = 1, 'Carla ve solo sus alertas');
update public.coincidencias set vista = true;
do $$ begin
  update public.coincidencias set avisado = false;
  raise exception 'FALLÓ: tocó una columna del servidor';
exception when insufficient_privilege then raise notice 'ok · solo puede marcar la alerta como vista';
end $$;
do $$ begin
  insert into public.coincidencias (busqueda_id, vehiculo_id, user_id) select busqueda_id, vehiculo_id, user_id from public.coincidencias;
  raise exception 'FALLÓ: creó una alerta desde la app';
exception when insufficient_privilege then raise notice 'ok · las alertas solo las crea el servidor';
end $$;
do $$ begin
  perform * from public.mis_clientes();
  perform public.contacto_cliente(gen_random_uuid());
  raise exception 'FALLÓ: alguien sin automotora pidió contactos';
exception when insufficient_privilege then raise notice 'ok · sin automotora no hay contactos';
end $$;

-- ═══ Beto mira sus clientes ═══
select set_config('request.jwt.claims', json_build_object('sub', :beto)::text, false);
select pg_temp.esperar((select count(*) from public.mis_clientes()) = 2, 'la automotora ve los 2 clientes que coinciden');
select pg_temp.esperar(public.cuantos_buscan() = 2, 'el plan Gratis ve cuántos buscan');
select pg_temp.esperar(not exists (select 1 from public.busquedas), 'la automotora no puede leer las búsquedas directamente');
do $$ begin
  perform public.contacto_cliente((select busqueda_id from public.mis_clientes() where autoriza_contacto limit 1));
  raise exception 'FALLÓ: vio un contacto con plan Gratis';
exception when insufficient_privilege then raise notice 'ok · con plan Gratis no ve contactos';
end $$;

-- El webhook de Mercado Pago confirma el cobro (servidor)
reset role;
update public.automotoras set plan = 'pro', plan_vence = now() + interval '1 month';
insert into public.pagos (automotora_id, mp_pago_id, plan, monto, estado, periodo_hasta)
select id, 'mp-1', 'pro', 1590, 'approved', now() + interval '1 month' from public.automotoras;
set role authenticated;

select set_config('request.jwt.claims', json_build_object('sub', :beto)::text, false);
select pg_temp.esperar(
  (select whatsapp from public.contacto_cliente((select busqueda_id from public.mis_clientes() where autoriza_contacto))) = '098111222',
  'con plan Pro ve el contacto de quien lo autorizó');
do $$ begin
  perform public.contacto_cliente((select busqueda_id from public.mis_clientes() where not autoriza_contacto));
  raise exception 'FALLÓ: vio el contacto de alguien que no autorizó';
exception when insufficient_privilege then raise notice 'ok · no ve el contacto de quien no lo autorizó';
end $$;
select pg_temp.esperar((select count(*) from public.pagos) = 1, 've su historial de pagos');

select set_config('request.jwt.claims', json_build_object('sub', :ana)::text, false);
select pg_temp.esperar((select count(*) from public.pagos) = 0, 'nadie más ve esos pagos');

-- Se vence el período pagado
reset role;
update public.automotoras set plan_vence = now() - interval '1 day';
set role authenticated;
select set_config('request.jwt.claims', json_build_object('sub', :beto)::text, false);
do $$ begin
  perform public.contacto_cliente((select busqueda_id from public.mis_clientes() where autoriza_contacto));
  raise exception 'FALLÓ: vio contactos con el plan vencido';
exception when insufficient_privilege then raise notice 'ok · con el plan vencido no ve contactos';
end $$;

-- ═══ Visitante sin cuenta ═══
reset role;
update public.automotoras set plan = 'destacado', plan_vence = now() + interval '1 month';
set role anon;
select set_config('request.jwt.claims', '', false);
select pg_temp.esperar((select count(*) from public.vehiculos_publicos) = 2, 'un visitante ve los vehículos activos');
select pg_temp.esperar((select destacado from public.vehiculos_publicos where modelo = 'Hilux'), 'la insignia de destacado sale del plan vigente');
do $$ begin
  perform * from public.busquedas;
  raise exception 'FALLÓ: un visitante leyó búsquedas';
exception when insufficient_privilege then raise notice 'ok · un visitante no puede leer búsquedas';
end $$;
do $$ begin
  perform plan from public.automotoras;
  raise exception 'FALLÓ: un visitante leyó el plan';
exception when insufficient_privilege then raise notice 'ok · un visitante no ve datos de facturación';
end $$;
do $$ begin
  perform * from public.mis_clientes();
  raise exception 'FALLÓ: un visitante llamó a mis_clientes';
exception when insufficient_privilege then raise notice 'ok · un visitante no puede pedir clientes';
end $$;
insert into public.denuncias (vehiculo_id, motivo, detalle) select id, 'estafa', 'Pide seña por adelantado' from public.vehiculos_publicos limit 1;
select pg_temp.esperar(true, 'cualquiera puede denunciar una publicación');
do $$ begin
  perform * from public.denuncias;
  raise exception 'FALLÓ: un visitante leyó denuncias';
exception when insufficient_privilege then raise notice 'ok · las denuncias no son públicas';
end $$;

-- ═══ Ana pausa su publicación ═══
set role authenticated;
select set_config('request.jwt.claims', json_build_object('sub', :ana)::text, false);
update public.vehiculos set estado = 'pausado' where modelo = 'Creta';
select pg_temp.esperar((select count(*) from public.vehiculos where modelo = 'Creta') = 1, 'la dueña sigue viendo su publicación pausada');
set role anon;
select set_config('request.jwt.claims', '', false);
select pg_temp.esperar((select count(*) from public.vehiculos_publicos where modelo = 'Creta') = 0, 'una publicación pausada no aparece en las búsquedas');

-- ═══ Borrar la cuenta borra todo ═══
reset role;
delete from auth.users where id = :ana;
select pg_temp.esperar((select count(*) from public.vehiculos where modelo = 'Creta') = 0, 'al borrar la cuenta se borran sus publicaciones');
delete from auth.users where id = :beto;
select pg_temp.esperar((select count(*) from public.automotoras) = 0 and (select count(*) from public.pagos) = 0, 'al borrar la cuenta de la automotora se borra su inventario y pagos');
delete from auth.users where id = :carla;
select pg_temp.esperar((select count(*) from public.busquedas) = 1, 'al borrar la cuenta se borran sus búsquedas');

\o
\echo '✔ Base y permisos: todo bien'
