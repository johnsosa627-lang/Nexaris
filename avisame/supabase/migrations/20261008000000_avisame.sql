-- ═══════════════════════════════════════════════════════════════════════════
-- Avisame · migración completa
--
-- Tablas, seguridad por fila (RLS), permisos por columna, almacenamiento de
-- fotos y funciones del servidor. Se aplica con `supabase db push` o pegándola
-- en el editor SQL de Supabase.
-- ═══════════════════════════════════════════════════════════════════════════

create extension if not exists pgcrypto;

-- ───────────────────────────── Perfiles ─────────────────────────────────────
-- Uno por usuario. Se crea solo cuando la persona ingresa por primera vez.

create table public.perfiles (
  id uuid primary key references auth.users (id) on delete cascade,
  nombre text check (char_length(nombre) <= 80),
  whatsapp text check (char_length(whatsapp) <= 20),
  push_token text check (char_length(push_token) <= 200),
  creado timestamptz not null default now()
);

alter table public.perfiles enable row level security;

create policy "perfil: ver el propio" on public.perfiles
  for select to authenticated using (id = auth.uid());
create policy "perfil: editar el propio" on public.perfiles
  for update to authenticated using (id = auth.uid()) with check (id = auth.uid());

revoke all on public.perfiles from anon, authenticated;
grant select on public.perfiles to authenticated;
grant update (nombre, whatsapp, push_token) on public.perfiles to authenticated;

create function public.crear_perfil() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.perfiles (id) values (new.id) on conflict do nothing;
  return new;
end $$;

create trigger crear_perfil after insert on auth.users
  for each row execute function public.crear_perfil();

-- ───────────────────────────── Automotoras ──────────────────────────────────
-- El plan solo lo cambia el servidor (webhook de Mercado Pago). La app no
-- tiene permiso sobre esas columnas.

create table public.automotoras (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null unique default auth.uid() references auth.users (id) on delete cascade,
  nombre text not null check (char_length(nombre) between 2 and 80),
  departamento text not null,
  ciudad text not null,
  direccion text check (char_length(direccion) <= 120),
  telefono text not null check (char_length(telefono) between 6 and 20),
  lat double precision not null check (lat between -35.5 and -29.5),
  lng double precision not null check (lng between -59 and -52.5),
  -- Plan (solo servidor)
  plan text not null default 'gratis' check (plan in ('gratis', 'pro', 'destacado')),
  plan_vence timestamptz,
  mp_preapproval_id text unique,
  mp_estado text,
  mp_plan_pendiente text check (mp_plan_pendiente in ('pro', 'destacado')),
  renovacion_cancelada boolean not null default false,
  creado timestamptz not null default now()
);

alter table public.automotoras enable row level security;

-- Datos públicos de la automotora (nombre, ciudad, teléfono): los ve cualquiera.
create policy "automotora: datos públicos" on public.automotoras
  for select to anon, authenticated using (true);
create policy "automotora: crear la propia" on public.automotoras
  for insert to authenticated with check (owner_id = auth.uid());
create policy "automotora: editar la propia" on public.automotoras
  for update to authenticated using (owner_id = auth.uid()) with check (owner_id = auth.uid());

revoke all on public.automotoras from anon, authenticated;
grant select (id, nombre, departamento, ciudad, direccion, telefono, lat, lng, creado)
  on public.automotoras to anon;
grant select (id, owner_id, nombre, departamento, ciudad, direccion, telefono, lat, lng, creado)
  on public.automotoras to authenticated;
grant insert (owner_id, nombre, departamento, ciudad, direccion, telefono, lat, lng)
  on public.automotoras to authenticated;
grant update (nombre, departamento, ciudad, direccion, telefono, lat, lng)
  on public.automotoras to authenticated;

-- Plan vigente: si el período pagado venció, vuelve a gratis.
create function public.plan_vigente(a public.automotoras) returns text
language sql stable as $$
  select case
    when a.plan in ('pro', 'destacado') and a.plan_vence > now() then a.plan
    else 'gratis'
  end
$$;

create function public.automotora_destacada(p_id uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select coalesce((select public.plan_vigente(a) = 'destacado' from public.automotoras a where a.id = p_id), false)
$$;

-- Estado del plan de la automotora propia (incluye columnas que no son públicas).
create function public.mi_automotora() returns table (
  id uuid, nombre text, departamento text, ciudad text, direccion text, telefono text,
  lat double precision, lng double precision, plan text, plan_vigente text, plan_vence timestamptz,
  mp_estado text, renovacion_cancelada boolean, tiene_suscripcion boolean
)
language sql stable security definer set search_path = public as $$
  select a.id, a.nombre, a.departamento, a.ciudad, a.direccion, a.telefono, a.lat, a.lng,
         a.plan, public.plan_vigente(a), a.plan_vence, a.mp_estado, a.renovacion_cancelada,
         a.mp_preapproval_id is not null
  from public.automotoras a where a.owner_id = auth.uid()
$$;

-- ───────────────────────────── Vehículos ────────────────────────────────────
-- Varias fuentes: publicaciones en Avisame, inventario de automotoras, la API
-- oficial de Mercado Libre y la importación del propio inventario de un
-- vendedor desde Facebook. Nada de scraping.

create table public.vehiculos (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid default auth.uid() references auth.users (id) on delete cascade,
  automotora_id uuid references public.automotoras (id) on delete cascade,
  source text not null default 'avisame' check (source in ('avisame', 'automotora', 'mercadolibre', 'facebook_propio')),
  external_id text,
  external_url text,
  marca text not null check (char_length(marca) between 1 and 40),
  modelo text not null check (char_length(modelo) between 1 and 40),
  version text check (char_length(version) <= 60),
  anio int not null check (anio between 1950 and 2100),
  km int not null check (km between 0 and 2000000),
  precio_usd int not null check (precio_usd between 100 and 5000000),
  transmision text not null check (transmision in ('manual', 'automatica')),
  combustible text not null check (combustible in ('nafta', 'diesel', 'hibrido', 'electrico')),
  tipo text not null check (tipo in ('sedan', 'hatch', 'suv', 'pickup', 'utilitario', 'otro')),
  traccion_4x4 boolean not null default false,
  descripcion text check (char_length(descripcion) <= 2000),
  departamento text not null,
  ciudad text not null,
  direccion text check (char_length(direccion) <= 120),
  lat double precision not null check (lat between -35.5 and -29.5),
  lng double precision not null check (lng between -59 and -52.5),
  fotos text[] not null default '{}' check (cardinality(fotos) between 1 and 10),
  contacto_nombre text not null check (char_length(contacto_nombre) between 1 and 80),
  contacto_whatsapp text not null check (char_length(contacto_whatsapp) between 6 and 20),
  estado text not null default 'activo' check (estado in ('activo', 'pausado', 'vendido')),
  creado timestamptz not null default now(),
  actualizado timestamptz not null default now(),
  unique (source, external_id),
  check (owner_id is not null or source in ('mercadolibre', 'facebook_propio')),
  check (source <> 'automotora' or automotora_id is not null)
);

create index vehiculos_busqueda on public.vehiculos (estado, lower(marca), lower(modelo));
create index vehiculos_owner on public.vehiculos (owner_id);
create index vehiculos_automotora on public.vehiculos (automotora_id);

alter table public.vehiculos enable row level security;

create policy "vehiculo: ver activos o propios" on public.vehiculos
  for select to anon, authenticated using (estado = 'activo' or owner_id = auth.uid());
create policy "vehiculo: publicar" on public.vehiculos
  for insert to authenticated with check (
    owner_id = auth.uid()
    and source in ('avisame', 'automotora')
    and (automotora_id is null or exists (
      select 1 from public.automotoras a where a.id = automotora_id and a.owner_id = auth.uid()))
  );
create policy "vehiculo: editar los propios" on public.vehiculos
  for update to authenticated using (owner_id = auth.uid()) with check (owner_id = auth.uid());
create policy "vehiculo: borrar los propios" on public.vehiculos
  for delete to authenticated using (owner_id = auth.uid());

revoke all on public.vehiculos from anon, authenticated;
grant select on public.vehiculos to anon, authenticated;
grant insert (owner_id, automotora_id, source, marca, modelo, version, anio, km, precio_usd, transmision,
  combustible, tipo, traccion_4x4, descripcion, departamento, ciudad, direccion, lat, lng, fotos,
  contacto_nombre, contacto_whatsapp)
  on public.vehiculos to authenticated;
grant update (marca, modelo, version, anio, km, precio_usd, transmision, combustible, tipo, traccion_4x4,
  descripcion, departamento, ciudad, direccion, lat, lng, fotos, contacto_nombre, contacto_whatsapp, estado)
  on public.vehiculos to authenticated;
grant delete on public.vehiculos to authenticated;

-- Los datos de la automotora se completan solos en cada vehículo que carga.
create function public.completar_vehiculo() returns trigger
language plpgsql security definer set search_path = public as $$
declare a public.automotoras;
begin
  new.actualizado := now();
  if new.automotora_id is not null then
    select * into a from public.automotoras where id = new.automotora_id;
    new.source := case when new.source = 'avisame' then 'automotora' else new.source end;
    new.contacto_nombre := a.nombre;
    new.contacto_whatsapp := a.telefono;
    -- Si no indicó otra ubicación, va la de la automotora.
    if tg_op = 'INSERT' and (new.departamento is null or new.departamento = '') then
      new.departamento := a.departamento; new.ciudad := a.ciudad; new.lat := a.lat; new.lng := a.lng;
    end if;
    if new.direccion is null or new.direccion = '' then new.direccion := a.direccion; end if;
  end if;
  return new;
end $$;

create trigger completar_vehiculo before insert or update on public.vehiculos
  for each row execute function public.completar_vehiculo();

-- Si la automotora cambia sus datos, se actualizan en su inventario.
create function public.propagar_automotora() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  update public.vehiculos set contacto_nombre = new.nombre, contacto_whatsapp = new.telefono
  where automotora_id = new.id;
  return new;
end $$;

create trigger propagar_automotora after update of nombre, telefono on public.automotoras
  for each row execute function public.propagar_automotora();

-- Vista para buscar: vehículos activos + insignia de destacado + nombre de la automotora.
create view public.vehiculos_publicos with (security_invoker = true) as
  select v.*,
         public.automotora_destacada(v.automotora_id) as destacado,
         a.nombre as automotora_nombre
  from public.vehiculos v
  left join public.automotoras a on a.id = v.automotora_id
  where v.estado = 'activo';

grant select on public.vehiculos_publicos to anon, authenticated;

-- ───────────────────────────── Búsquedas guardadas ──────────────────────────

create table public.busquedas (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  texto text not null check (char_length(texto) <= 300),
  criterios jsonb not null default '{}',
  nombre text not null check (char_length(nombre) between 1 and 80),
  whatsapp text not null check (char_length(whatsapp) between 6 and 20),
  autoriza_contacto boolean not null default false,
  departamento text not null,
  ciudad text not null,
  lat double precision not null,
  lng double precision not null,
  activa boolean not null default true,
  creado timestamptz not null default now()
);

create index busquedas_activas on public.busquedas (activa);

alter table public.busquedas enable row level security;

create policy "búsqueda: ver las propias" on public.busquedas
  for select to authenticated using (user_id = auth.uid());
create policy "búsqueda: guardar" on public.busquedas
  for insert to authenticated with check (user_id = auth.uid());
create policy "búsqueda: editar las propias" on public.busquedas
  for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "búsqueda: borrar las propias" on public.busquedas
  for delete to authenticated using (user_id = auth.uid());

revoke all on public.busquedas from anon, authenticated;
grant select, delete on public.busquedas to authenticated;
grant insert (user_id, texto, criterios, nombre, whatsapp, autoriza_contacto, departamento, ciudad, lat, lng)
  on public.busquedas to authenticated;
grant update (nombre, whatsapp, autoriza_contacto, activa) on public.busquedas to authenticated;

-- ───────────────────────────── Coincidencias (alertas) ──────────────────────
-- Las escribe solo la función `match`. Una fila por búsqueda y vehículo: así
-- nunca se repite un aviso.

create table public.coincidencias (
  id uuid primary key default gen_random_uuid(),
  busqueda_id uuid not null references public.busquedas (id) on delete cascade,
  vehiculo_id uuid not null references public.vehiculos (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  distancia_km int,
  avisado boolean not null default false,
  vista boolean not null default false,
  creado timestamptz not null default now(),
  unique (busqueda_id, vehiculo_id)
);

create index coincidencias_usuario on public.coincidencias (user_id, creado desc);
create index coincidencias_vehiculo on public.coincidencias (vehiculo_id);

alter table public.coincidencias enable row level security;

create policy "alerta: ver las propias" on public.coincidencias
  for select to authenticated using (user_id = auth.uid());
create policy "alerta: marcar como vista" on public.coincidencias
  for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

revoke all on public.coincidencias from anon, authenticated;
grant select on public.coincidencias to authenticated;
grant update (vista) on public.coincidencias to authenticated;

-- Avisos ya enviados a cada automotora por cada cliente (para no repetir).
create table public.avisos_automotora (
  automotora_id uuid not null references public.automotoras (id) on delete cascade,
  busqueda_id uuid not null references public.busquedas (id) on delete cascade,
  creado timestamptz not null default now(),
  primary key (automotora_id, busqueda_id)
);

alter table public.avisos_automotora enable row level security;
revoke all on public.avisos_automotora from anon, authenticated;

-- ───────────────────────────── Clientes de la automotora ────────────────────
-- Búsquedas guardadas que coinciden con su inventario. Nunca devuelve el
-- contacto: para eso está `contacto_cliente`.

create function public.mis_clientes() returns table (
  busqueda_id uuid, texto text, criterios jsonb, departamento text, ciudad text,
  lat double precision, lng double precision, creado timestamptz,
  vehiculos jsonb, autoriza_contacto boolean
)
language sql stable security definer set search_path = public as $$
  select b.id, b.texto, b.criterios, b.departamento, b.ciudad, b.lat, b.lng, b.creado,
         jsonb_agg(jsonb_build_object('id', v.id, 'marca', v.marca, 'modelo', v.modelo, 'anio', v.anio) order by v.creado desc),
         b.autoriza_contacto
  from public.automotoras a
  join public.vehiculos v on v.automotora_id = a.id and v.estado = 'activo'
  join public.coincidencias c on c.vehiculo_id = v.id
  join public.busquedas b on b.id = c.busqueda_id and b.activa
  where a.owner_id = auth.uid()
  group by b.id
  order by b.creado desc
$$;

-- Contacto de un cliente: solo con plan pago al día Y si el cliente lo autorizó
-- Y si la búsqueda coincide con un vehículo activo de la automotora.
create function public.contacto_cliente(p_busqueda uuid) returns table (nombre text, whatsapp text)
language plpgsql stable security definer set search_path = public as $$
declare a public.automotoras;
begin
  select * into a from public.automotoras where owner_id = auth.uid();
  if a.id is null then
    raise exception 'No tenés una automotora registrada' using errcode = '42501';
  end if;
  if public.plan_vigente(a) not in ('pro', 'destacado') then
    raise exception 'Necesitás el plan Pro o Destacado al día para ver el contacto' using errcode = '42501';
  end if;
  return query
    select b.nombre, b.whatsapp
    from public.busquedas b
    where b.id = p_busqueda and b.activa and b.autoriza_contacto
      and exists (
        select 1 from public.coincidencias c join public.vehiculos v on v.id = c.vehiculo_id
        where c.busqueda_id = b.id and v.automotora_id = a.id and v.estado = 'activo');
  if not found then
    raise exception 'Este cliente no autorizó que lo contacten' using errcode = '42501';
  end if;
end $$;

-- Cuántas personas buscan algo de mi inventario (lo ve cualquier plan).
create function public.cuantos_buscan() returns int
language sql stable security definer set search_path = public as $$
  select count(*)::int from public.mis_clientes()
$$;

revoke execute on function public.mis_clientes() from public, anon;
revoke execute on function public.contacto_cliente(uuid) from public, anon;
revoke execute on function public.cuantos_buscan() from public, anon;
revoke execute on function public.mi_automotora() from public, anon;
grant execute on function public.mis_clientes() to authenticated;
grant execute on function public.contacto_cliente(uuid) to authenticated;
grant execute on function public.cuantos_buscan() to authenticated;
grant execute on function public.mi_automotora() to authenticated;

-- ───────────────────────────── Pagos ────────────────────────────────────────

create table public.pagos (
  id uuid primary key default gen_random_uuid(),
  automotora_id uuid not null references public.automotoras (id) on delete cascade,
  mp_pago_id text not null unique,
  mp_preapproval_id text,
  plan text not null check (plan in ('pro', 'destacado')),
  monto numeric(10, 2) not null,
  moneda text not null default 'UYU',
  estado text not null,
  periodo_hasta timestamptz,
  creado timestamptz not null default now()
);

alter table public.pagos enable row level security;

create policy "pago: ver los de mi automotora" on public.pagos
  for select to authenticated using (
    exists (select 1 from public.automotoras a where a.id = automotora_id and a.owner_id = auth.uid()));

revoke all on public.pagos from anon, authenticated;
grant select on public.pagos to authenticated;

-- ───────────────────────────── Denuncias ────────────────────────────────────

create table public.denuncias (
  id uuid primary key default gen_random_uuid(),
  vehiculo_id uuid not null references public.vehiculos (id) on delete cascade,
  user_id uuid references auth.users (id) on delete set null,
  motivo text not null check (motivo in ('estafa', 'vendido', 'datos_falsos', 'ofensivo', 'otro')),
  detalle text check (char_length(detalle) <= 500),
  creado timestamptz not null default now()
);

alter table public.denuncias enable row level security;

create policy "denuncia: cualquiera puede denunciar" on public.denuncias
  for insert to anon, authenticated with check (user_id is null or user_id = auth.uid());

revoke all on public.denuncias from anon, authenticated;
grant insert (vehiculo_id, user_id, motivo, detalle) on public.denuncias to anon, authenticated;

-- ───────────────────────────── Fotos (Storage) ──────────────────────────────
-- Bucket público para leer; cada usuario sube, cambia y borra solo en su
-- carpeta: fotos/<id del usuario>/...

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('fotos', 'fotos', true, 5242880, array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do nothing;

create policy "fotos: subir a mi carpeta" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'fotos' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "fotos: cambiar en mi carpeta" on storage.objects
  for update to authenticated
  using (bucket_id = 'fotos' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "fotos: borrar de mi carpeta" on storage.objects
  for delete to authenticated
  using (bucket_id = 'fotos' and (storage.foldername(name))[1] = auth.uid()::text);
