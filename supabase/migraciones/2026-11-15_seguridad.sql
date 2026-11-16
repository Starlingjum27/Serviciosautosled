-- =====================================================================
--  SEGURIDAD · permisos de la base de datos (Servicios Autos LED)
--  Fecha: 2026-11-15
--
--  Qué corrige:
--    1. Configuración: hoy cualquier usuario puede cambiarla desde la API
--       (por ejemplo, ponerse como administrador). → Solo administradores.
--    2. Productos, proveedores, clientes, categorías y tasa BCV: cualquiera
--       puede BORRAR. → Crear y editar sigue abierto; borrar, solo administradores.
--    3. Cambios de precio/costo y productos borrados no quedaban en auditoría. → Ahora sí.
--    4. Tabla usuarios: cualquiera podía cambiarse el rol. → Solo administradores.
--    5. Las funciones (cfg, registrar_venta, …) se podían llamar SIN iniciar sesión
--       con la clave pública. → Solo usuarios con sesión.
--
--  No cambia el comportamiento de hoy mientras la lista de administradores esté vacía
--  (lista vacía = todos son administradores, igual que la app). Después de correrlo,
--  ve a Configuración → Seguridad en la app y escribe el/los correo(s) administrador(es).
--
--  Cómo correrlo: Supabase → SQL Editor → pega todo → Run.
--  Va dentro de una transacción: si algo falla, no se aplica nada.
-- =====================================================================
begin;

-- ---------------------------------------------------------------------
-- 1) ¿El usuario actual es administrador?
--    Misma regla que la app y que anular_venta / anular_compra.
-- ---------------------------------------------------------------------
create or replace function public.es_admin()
returns boolean
language sql
stable
security definer
set search_path to 'public'
as $$
  select auth.uid() is not null and (
    replace(coalesce(public.cfg('emails_administradores', ''), ''), ' ', '') = ''
    or lower(coalesce(auth.jwt() ->> 'email', '')) = any (
         string_to_array(lower(replace(public.cfg('emails_administradores', ''), ' ', '')), ','))
  )
$$;

-- ---------------------------------------------------------------------
-- 2) Configuración: todos leen, solo administradores escriben
-- ---------------------------------------------------------------------
drop policy if exists autenticados_todo     on public.configuracion;
drop policy if exists autenticados_lectura  on public.configuracion;
drop policy if exists admin_escritura       on public.configuracion;

create policy autenticados_lectura on public.configuracion
  for select to authenticated using (true);
create policy admin_escritura on public.configuracion
  for all to authenticated using (public.es_admin()) with check (public.es_admin());

-- ---------------------------------------------------------------------
-- 3) Catálogos: leer, crear y editar = cualquier usuario con sesión;
--    borrar = solo administradores.
--    (tasas_bcv necesita crear/editar abierto: la tasa automática se guarda
--     al iniciar sesión cualquier usuario; sus cambios ya van a auditoría.)
-- ---------------------------------------------------------------------
do $$
declare
  t text;
begin
  foreach t in array array['productos', 'proveedores', 'clientes', 'categorias', 'tasas_bcv'] loop
    execute format('drop policy if exists autenticados_todo on public.%I', t);
    execute format('drop policy if exists "Permitir lectura a usuarios autenticados" on public.%I', t);
    execute format('drop policy if exists autenticados_lectura on public.%I', t);
    execute format('drop policy if exists autenticados_crear on public.%I', t);
    execute format('drop policy if exists autenticados_editar on public.%I', t);
    execute format('drop policy if exists admin_borrar on public.%I', t);

    execute format('create policy autenticados_lectura on public.%I for select to authenticated using (true)', t);
    execute format('create policy autenticados_crear on public.%I for insert to authenticated with check (true)', t);
    execute format('create policy autenticados_editar on public.%I for update to authenticated using (true) with check (true)', t);
    execute format('create policy admin_borrar on public.%I for delete to authenticated using (public.es_admin())', t);
  end loop;
end $$;

-- ---------------------------------------------------------------------
-- 4) Auditoría de productos: cambios de precio/costo hechos a mano y borrados
--    (las compras ya guardan costo/precio anterior y nuevo en detalle_compras)
-- ---------------------------------------------------------------------
create or replace function public.trg_productos_auditoria()
returns trigger
language plpgsql
security definer
set search_path to 'public'
as $$
begin
  if tg_op = 'DELETE' then
    insert into public.auditoria (accion, entidad, entidad_id, datos)
    values ('BORRAR', 'productos', old.id::text, to_jsonb(old));
    return old;
  end if;

  if coalesce(current_setting('app.origen_stock', true), '') = 'rpc' then
    return new;
  end if;

  if new.precio_usd is distinct from old.precio_usd or new.costo_usd is distinct from old.costo_usd then
    insert into public.auditoria (accion, entidad, entidad_id, datos)
    values ('CAMBIO_PRECIO', 'productos', new.id::text, jsonb_build_object(
      'sku', new.sku,
      'precio_anterior', old.precio_usd, 'precio_nuevo', new.precio_usd,
      'costo_anterior',  old.costo_usd,  'costo_nuevo',  new.costo_usd));
  end if;
  return new;
end $$;

drop trigger if exists productos_auditoria on public.productos;
create trigger productos_auditoria
  after update of precio_usd, costo_usd or delete on public.productos
  for each row execute function public.trg_productos_auditoria();

-- ---------------------------------------------------------------------
-- 5) Usuarios y roles: cada quien ve su fila; solo administradores modifican
-- ---------------------------------------------------------------------
drop policy if exists autenticados_todo   on public.usuarios;
drop policy if exists ver_propio_o_admin  on public.usuarios;
drop policy if exists admin_escritura     on public.usuarios;

create policy ver_propio_o_admin on public.usuarios
  for select to authenticated using (id = auth.uid() or public.es_admin());
create policy admin_escritura on public.usuarios
  for all to authenticated using (public.es_admin()) with check (public.es_admin());

-- ---------------------------------------------------------------------
-- 6) Funciones: solo usuarios con sesión (nada para "anon")
-- ---------------------------------------------------------------------
revoke execute on function public.es_admin()                         from public, anon;
revoke execute on function public.cfg(text, text)                    from public, anon;
revoke execute on function public.tasa_vigente(date)                 from public, anon;
revoke execute on function public.registrar_venta(jsonb, jsonb, jsonb, text, uuid, boolean) from public, anon;
revoke execute on function public.registrar_compra(bigint, jsonb, jsonb, numeric, numeric, numeric, text, text, uuid) from public, anon;
revoke execute on function public.anular_venta(bigint, text)         from public, anon;
revoke execute on function public.anular_compra(bigint, text)        from public, anon;

grant execute on function public.es_admin()                          to authenticated;
grant execute on function public.cfg(text, text)                     to authenticated;
grant execute on function public.tasa_vigente(date)                  to authenticated;
grant execute on function public.registrar_venta(jsonb, jsonb, jsonb, text, uuid, boolean) to authenticated;
grant execute on function public.registrar_compra(bigint, jsonb, jsonb, numeric, numeric, numeric, text, text, uuid) to authenticated;
grant execute on function public.anular_venta(bigint, text)          to authenticated;
grant execute on function public.anular_compra(bigint, text)         to authenticated;

commit;

-- ---------------------------------------------------------------------
-- Comprobación (solo lectura): políticas resultantes y quién puede ejecutar cfg
-- ---------------------------------------------------------------------
select tablename, policyname, cmd, roles
from pg_policies
where schemaname = 'public'
  and tablename in ('configuracion', 'productos', 'proveedores', 'clientes', 'categorias', 'tasas_bcv', 'usuarios')
order by tablename, cmd;
