-- =====================================================================
--  SERVICIOS (mano de obra) · Servicios Autos LED
--  Fecha: 2026-11-16
--
--  Agrega el tipo de ítem SERVICIO (instalación, diagnóstico, mano de obra…):
--    · Se vende igual que un producto, pero NO lleva stock ni mueve el kardex.
--    · Puede cobrarse a precio libre en el punto de venta y llevar una nota
--      (ej. "Instalación de faros · Corolla 2015"), que sale en el comprobante.
--    · No se puede comprar ni ajustar su stock.
--    · Al anular una venta, los servicios no "devuelven" inventario.
--
--  Compatible con la app actual: todo lo existente queda como PRODUCTO.
--  Cómo correrlo: Supabase → SQL Editor → pega todo → Run.
--  Va dentro de una transacción: si algo falla, no se aplica nada.
-- =====================================================================
begin;

-- ---------------------------------------------------------------------
-- 1) Columnas nuevas
-- ---------------------------------------------------------------------
alter table public.productos
  add column if not exists tipo text not null default 'PRODUCTO';

alter table public.productos drop constraint if exists productos_tipo_check;
alter table public.productos
  add constraint productos_tipo_check check (tipo in ('PRODUCTO', 'SERVICIO'));

alter table public.productos drop constraint if exists productos_servicio_sin_stock;
alter table public.productos
  add constraint productos_servicio_sin_stock check (tipo = 'PRODUCTO' or coalesce(stock_actual, 0) = 0);

alter table public.detalle_ventas
  add column if not exists es_servicio boolean not null default false;

-- ---------------------------------------------------------------------
-- 2) Mensaje claro si algo intenta darle stock a un servicio
--    (compras, ajustes manuales, cambio de tipo con stock)
-- ---------------------------------------------------------------------
create or replace function public.trg_productos_servicio_sin_stock()
returns trigger
language plpgsql
set search_path to 'public'
as $$
begin
  if new.tipo = 'SERVICIO' and coalesce(new.stock_actual, 0) <> 0 then
    raise exception '% es un servicio: no lleva inventario (no se compra ni se le ajusta stock).', new.sku;
  end if;
  return new;
end $$;

drop trigger if exists productos_servicio_sin_stock on public.productos;
create trigger productos_servicio_sin_stock
  before insert or update of stock_actual, tipo on public.productos
  for each row execute function public.trg_productos_servicio_sin_stock();

-- ---------------------------------------------------------------------
-- 3) registrar_venta: servicios sin stock, precio libre y nota
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.registrar_venta(p_items jsonb, p_pagos jsonb, p_cliente jsonb DEFAULT '{}'::jsonb, p_observaciones text DEFAULT NULL::text, p_idempotency_key uuid DEFAULT NULL::uuid, p_aplicar_iva boolean DEFAULT true)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_uid        uuid := auth.uid();
  v_email      text := coalesce(auth.jwt() ->> 'email', '');
  v_fecha_tasa date;
  v_tasa       numeric;
  v_iva_pct    numeric := case when coalesce(p_aplicar_iva, true)
                               then public.cfg('iva_porcentaje', '16')::numeric else 0 end;
  v_igtf_pct   numeric := case when public.cfg('igtf_activo', 'false')::boolean
                               then public.cfg('igtf_porcentaje', '3')::numeric else 0 end;
  v_desc_max   numeric := public.cfg('descuento_max_pct', '10')::numeric;
  v_sin_stock  boolean := public.cfg('permitir_venta_sin_stock', 'false')::boolean;
  v_dias_max   int     := public.cfg('tasa_dias_max', '4')::int;
  v_item       record;
  v_prod       record;
  v_linea      jsonb;
  v_lineas     jsonb := '[]'::jsonb;
  v_sub        numeric;
  v_exento_usd numeric := 0;
  v_base_usd   numeric := 0;
  v_iva_usd    numeric;
  v_total_usd  numeric;
  v_exento_bs  numeric;
  v_base_bs    numeric;
  v_iva_bs     numeric;
  v_total_bs   numeric;
  v_usd_ent    numeric := 0;
  v_bs_ent     numeric := 0;
  v_divisas    numeric;
  v_igtf_usd   numeric;
  v_igtf_bs    numeric;
  v_bs_req     numeric;
  v_cliente_id bigint;
  v_rif        text;
  v_nombre     text;
  v_venta_id   bigint;
  v_numero     text;
  v_cant       numeric;
  v_existente  record;
  v_servicio   boolean;
  v_precio     numeric;
begin
  if v_uid is null then
    raise exception 'Sesión no válida. Cierra sesión e ingresa de nuevo.';
  end if;

  -- Idempotencia: si el mismo carrito ya se procesó (doble clic), devolver esa venta
  if p_idempotency_key is not null then
    select id, numero into v_existente from public.ventas where idempotency_key = p_idempotency_key;
    if found then
      return jsonb_build_object('venta_id', v_existente.id, 'numero', v_existente.numero, 'repetida', true);
    end if;
  end if;

  if p_items is null or jsonb_typeof(p_items) <> 'array' or jsonb_array_length(p_items) = 0 then
    raise exception 'El carrito está vacío.';
  end if;
  p_pagos := coalesce(p_pagos, '[]'::jsonb);

  -- Tasa BCV vigente
  select tv.fecha_tasa, tv.tasa into v_fecha_tasa, v_tasa from public.tasa_vigente() tv;
  if v_tasa is null then
    raise exception 'No hay tasa BCV registrada. Regístrala en el módulo Tasa BCV.';
  end if;
  if public.fecha_vzla() - v_fecha_tasa > v_dias_max then
    raise exception 'La última tasa BCV es del %, tiene más de % días. Actualízala antes de vender.',
      to_char(v_fecha_tasa, 'DD/MM/YYYY'), v_dias_max;
  end if;

  -- Cliente
  v_rif    := upper(regexp_replace(coalesce(p_cliente ->> 'rif', ''), '\s', '', 'g'));
  v_nombre := nullif(trim(coalesce(p_cliente ->> 'nombre', '')), '');
  if v_rif = '' then
    v_rif := 'V-00000000';
    v_nombre := coalesce(v_nombre, 'CONSUMIDOR FINAL');
  end if;
  if v_rif !~ '^[VEJGP]-[0-9]{5,9}(-[0-9])?$' then
    raise exception 'RIF/Cédula inválido: %. Formato esperado V-12345678 o J-12345678-9.', v_rif;
  end if;
  if v_nombre is null then
    select c.nombre into v_nombre from public.clientes c where c.rif = v_rif;
  end if;
  if v_nombre is null then
    raise exception 'Indica el nombre o razón social del cliente.';
  end if;

  insert into public.clientes (rif, nombre, telefono, direccion)
  values (v_rif, upper(v_nombre),
          nullif(trim(coalesce(p_cliente ->> 'telefono', '')), ''),
          nullif(trim(coalesce(p_cliente ->> 'direccion', '')), ''))
  on conflict (rif) do update
     set nombre     = excluded.nombre,
         telefono   = coalesce(excluded.telefono, public.clientes.telefono),
         direccion  = coalesce(excluded.direccion, public.clientes.direccion),
         updated_at = now()
  returning id into v_cliente_id;

  -- Desde aquí, el kardex lo escribe esta función (el trigger se hace a un lado)
  perform set_config('app.origen_stock', 'rpc', true);

  -- 1ª pasada: bloquear productos (en orden de id para evitar deadlocks), validar y calcular
  --    Los SERVICIOS no llevan stock y pueden cobrarse a precio libre ('precio_usd') con una 'nota'.
  for v_item in
    select (e ->> 'producto_id')::bigint                     as producto_id,
           case when pr.tipo = 'SERVICIO' then nullif(e ->> 'precio_usd', '')::numeric end         as precio_libre,
           case when pr.tipo = 'SERVICIO' then nullif(trim(coalesce(e ->> 'nota', '')), '') end as nota,
           sum((e ->> 'cantidad')::numeric)                  as cantidad,
           max(coalesce((e ->> 'descuento_pct')::numeric, 0)) as descuento_pct
    from jsonb_array_elements(p_items) e
    left join public.productos pr on pr.id = (e ->> 'producto_id')::bigint
    group by 1, 2, 3
    order by 1, 2, 3
  loop
    if v_item.cantidad is null or v_item.cantidad <= 0 or v_item.cantidad <> trunc(v_item.cantidad) then
      raise exception 'Cantidad inválida para el producto %.', v_item.producto_id;
    end if;
    if v_item.descuento_pct < 0 or v_item.descuento_pct > v_desc_max then
      raise exception 'El descuento (% %%) supera el máximo permitido (% %%).', v_item.descuento_pct, v_desc_max;
    end if;

    select * into v_prod from public.productos where id = v_item.producto_id for update;
    if not found then
      raise exception 'El producto % ya no existe.', v_item.producto_id;
    end if;
    if not coalesce(v_prod.activo, true) then
      raise exception 'El producto % está inactivo.', v_prod.sku;
    end if;
    v_servicio := coalesce(v_prod.tipo, 'PRODUCTO') = 'SERVICIO';
    v_precio   := round(coalesce(v_item.precio_libre, v_prod.precio_usd)::numeric, 2);
    if coalesce(v_precio, 0) <= 0 then
      raise exception 'El producto % no tiene precio de venta.', v_prod.sku;
    end if;
    if not v_servicio and not v_sin_stock and coalesce(v_prod.stock_actual, 0) < v_item.cantidad then
      raise exception 'Stock insuficiente para % (%): disponible %, solicitado %.',
        v_prod.sku, v_prod.nombre, coalesce(v_prod.stock_actual, 0), v_item.cantidad;
    end if;

    v_sub := round(v_precio * v_item.cantidad * (1 - v_item.descuento_pct / 100), 2);
    if coalesce(v_prod.exento_iva, false) then
      v_exento_usd := v_exento_usd + v_sub;
    else
      v_base_usd := v_base_usd + v_sub;
    end if;

    v_lineas := v_lineas || jsonb_build_object(
      'producto_id', v_prod.id, 'sku', v_prod.sku,
      'descripcion', v_prod.nombre || coalesce(' · ' || v_item.nota, ''),
      'cantidad', v_item.cantidad, 'precio', v_precio, 'servicio', v_servicio,
      'descuento', v_item.descuento_pct, 'subtotal', v_sub,
      'exento', coalesce(v_prod.exento_iva, false),
      'costo', coalesce(v_prod.costo_usd, 0), 'stock', coalesce(v_prod.stock_actual, 0));
  end loop;

  -- Totales: el IVA se calcula sobre el monto en BOLÍVARES
  v_iva_usd   := round(v_base_usd * v_iva_pct / 100, 2);
  v_total_usd := v_exento_usd + v_base_usd + v_iva_usd;
  v_exento_bs := round(v_exento_usd * v_tasa, 2);
  v_base_bs   := round(v_base_usd * v_tasa, 2);
  v_iva_bs    := round(v_base_bs * v_iva_pct / 100, 2);
  v_total_bs  := v_exento_bs + v_base_bs + v_iva_bs;

  -- Pagos
  if exists (select 1 from jsonb_array_elements(p_pagos) e
             where coalesce((e ->> 'monto')::numeric, 0) <= 0
                or coalesce(e ->> 'moneda', '') not in ('USD', 'VES')) then
    raise exception 'Hay un pago con monto o moneda inválidos.';
  end if;

  select coalesce(sum((e ->> 'monto')::numeric) filter (where e ->> 'moneda' = 'USD'), 0),
         coalesce(sum((e ->> 'monto')::numeric) filter (where e ->> 'moneda' = 'VES'), 0)
    into v_usd_ent, v_bs_ent
  from jsonb_array_elements(p_pagos) e;

  -- IGTF: solo sobre la porción de la factura pagada en divisas.
  -- Lo entregado en divisas cubre "porción + IGTF de esa porción".
  v_divisas  := least(round(v_usd_ent / (1 + v_igtf_pct / 100), 2), v_total_usd);
  v_igtf_usd := round(v_divisas * v_igtf_pct / 100, 2);
  v_igtf_bs  := round(v_igtf_usd * v_tasa, 2);

  if v_divisas >= v_total_usd then
    v_bs_req := 0;
  else
    v_bs_req := greatest(v_total_bs - round(v_divisas * v_tasa, 2), 0);
  end if;

  if v_bs_ent + 0.009 < v_bs_req then
    raise exception 'Pago incompleto: faltan Bs. %.', to_char(v_bs_req - v_bs_ent, 'FM999999990.00');
  end if;

  -- Cabecera
  v_numero := public.cfg('serie_documento', 'NE') || '-' || lpad(nextval('public.seq_documento_venta')::text, 8, '0');

  insert into public.ventas (
    numero, idempotency_key, aplica_iva, fecha_tasa, tasa_bcv, cliente_id, cliente_rif, cliente_nombre,
    exento_usd, base_imponible_usd, iva_porcentaje, iva_usd, total_usd,
    exento_bs, base_imponible_bs, iva_bs, total_bs,
    pagado_divisas_usd, igtf_porcentaje, igtf_usd, igtf_bs,
    total_pagar_usd, total_pagar_bs, vuelto_usd, vuelto_bs,
    observaciones, usuario_id, usuario_email)
  values (
    v_numero, p_idempotency_key, coalesce(p_aplicar_iva, true), v_fecha_tasa, v_tasa, v_cliente_id, v_rif, upper(v_nombre),
    v_exento_usd, v_base_usd, v_iva_pct, v_iva_usd, v_total_usd,
    v_exento_bs, v_base_bs, v_iva_bs, v_total_bs,
    v_divisas, v_igtf_pct, v_igtf_usd, v_igtf_bs,
    v_total_usd + v_igtf_usd, v_total_bs + v_igtf_bs,
    greatest(v_usd_ent - v_divisas - v_igtf_usd, 0), greatest(v_bs_ent - v_bs_req, 0),
    nullif(trim(coalesce(p_observaciones, '')), ''), v_uid, v_email)
  returning id into v_venta_id;

  -- 2ª pasada: detalle, descuento de stock y kardex
  for v_linea in select value from jsonb_array_elements(v_lineas) loop
    v_cant := (v_linea ->> 'cantidad')::numeric;

    insert into public.detalle_ventas (
      venta_id, producto_id, sku, descripcion, cantidad, precio_unitario_usd, descuento_pct,
      subtotal_usd, exento_iva, costo_unitario_usd, tasa_bcv, subtotal_bs, es_servicio)
    values (
      v_venta_id, (v_linea ->> 'producto_id')::bigint, v_linea ->> 'sku', v_linea ->> 'descripcion',
      v_cant::int, (v_linea ->> 'precio')::numeric, (v_linea ->> 'descuento')::numeric,
      (v_linea ->> 'subtotal')::numeric, (v_linea ->> 'exento')::boolean,
      (v_linea ->> 'costo')::numeric, v_tasa, round((v_linea ->> 'subtotal')::numeric * v_tasa, 2),
      (v_linea ->> 'servicio')::boolean);

    if (v_linea ->> 'servicio')::boolean then
      continue;  -- los servicios no mueven inventario ni kardex
    end if;

    update public.productos
       set stock_actual = stock_actual - v_cant, updated_at = now()
     where id = (v_linea ->> 'producto_id')::bigint;

    insert into public.movimientos_inventario (
      producto_id, tipo, motivo, cantidad, stock_anterior, stock_nuevo, costo_unitario_usd,
      tasa_bcv, costo_total_bs, documento_tipo, documento_id, usuario_id, observacion)
    values (
      (v_linea ->> 'producto_id')::bigint, 'SALIDA', 'VENTA', v_cant,
      (v_linea ->> 'stock')::numeric, (v_linea ->> 'stock')::numeric - v_cant,
      (v_linea ->> 'costo')::numeric, v_tasa,
      round(v_cant * (v_linea ->> 'costo')::numeric * v_tasa, 2),
      'VENTA', v_venta_id, v_uid, v_numero);
  end loop;

  insert into public.pagos_venta (venta_id, metodo, moneda, monto, referencia)
  select v_venta_id, coalesce(nullif(e ->> 'metodo', ''), 'N/D'), e ->> 'moneda',
         round((e ->> 'monto')::numeric, 2), nullif(trim(coalesce(e ->> 'referencia', '')), '')
  from jsonb_array_elements(p_pagos) e;

  insert into public.auditoria (usuario_id, accion, entidad, entidad_id, datos)
  values (v_uid, 'CREAR', 'ventas', v_venta_id::text,
          jsonb_build_object('numero', v_numero, 'total_usd', v_total_usd, 'total_bs', v_total_bs,
                             'tasa', v_tasa, 'igtf_usd', v_igtf_usd,
                             'aplica_iva', coalesce(p_aplicar_iva, true)));

  return jsonb_build_object('venta_id', v_venta_id, 'numero', v_numero, 'repetida', false,
                            'total_pagar_usd', v_total_usd + v_igtf_usd,
                            'total_pagar_bs', v_total_bs + v_igtf_bs);
end $function$
;

CREATE OR REPLACE FUNCTION public.tasa_vigente(p_fecha date DEFAULT NULL::date)
 RETURNS TABLE(fecha_tasa date, tasa numeric)
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select t.fecha::date, t.tasa::numeric
  from public.tasas_bcv t
  where t.fecha::date <= coalesce(p_fecha, public.fecha_vzla())
    and t.tasa::numeric > 0
  order by t.fecha::date desc
  limit 1
$function$
;

-- ---------------------------------------------------------------------
-- 4) anular_venta: los servicios no devuelven inventario
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.anular_venta(p_venta_id bigint, p_motivo text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_uid    uuid := auth.uid();
  v_email  text := lower(coalesce(auth.jwt() ->> 'email', ''));
  v_admins text := lower(replace(public.cfg('emails_administradores', ''), ' ', ''));
  v_venta  public.ventas%rowtype;
  v_det    record;
  v_stock  numeric;
  v_nc     text;
begin
  if v_uid is null then
    raise exception 'Sesión no válida.';
  end if;
  if v_admins <> '' and not (v_email = any (string_to_array(v_admins, ','))) then
    raise exception 'Solo un administrador puede anular ventas.';
  end if;
  if length(trim(coalesce(p_motivo, ''))) < 10 then
    raise exception 'Indica un motivo de al menos 10 caracteres.';
  end if;

  select * into v_venta from public.ventas where id = p_venta_id for update;
  if not found then
    raise exception 'La venta no existe.';
  end if;
  if v_venta.estado = 'ANULADA' then
    raise exception 'La venta % ya está anulada.', v_venta.numero;
  end if;

  perform set_config('app.origen_stock', 'rpc', true);
  v_nc := 'NC-' || lpad(nextval('public.seq_nota_credito')::text, 8, '0');

  for v_det in select * from public.detalle_ventas where venta_id = p_venta_id order by producto_id loop
    if v_det.es_servicio then
      continue;  -- los servicios no devuelven inventario
    end if;
    select coalesce(stock_actual, 0) into v_stock from public.productos where id = v_det.producto_id for update;

    update public.productos
       set stock_actual = coalesce(stock_actual, 0) + v_det.cantidad, updated_at = now()
     where id = v_det.producto_id;

    insert into public.movimientos_inventario (
      producto_id, tipo, motivo, cantidad, stock_anterior, stock_nuevo, costo_unitario_usd,
      tasa_bcv, costo_total_bs, documento_tipo, documento_id, usuario_id, observacion)
    values (
      v_det.producto_id, 'ENTRADA', 'ANULACION_VENTA', v_det.cantidad, v_stock, v_stock + v_det.cantidad,
      v_det.costo_unitario_usd, v_venta.tasa_bcv,
      round(v_det.cantidad * v_det.costo_unitario_usd * v_venta.tasa_bcv, 2),
      'VENTA', p_venta_id, v_uid, v_nc || ' anula ' || v_venta.numero);
  end loop;

  insert into public.notas_credito (numero, venta_id, tasa_bcv, total_usd, total_bs, igtf_usd, igtf_bs, motivo, usuario_id)
  values (v_nc, p_venta_id, v_venta.tasa_bcv, v_venta.total_usd, v_venta.total_bs,
          v_venta.igtf_usd, v_venta.igtf_bs, trim(p_motivo), v_uid);

  update public.ventas
     set estado = 'ANULADA', anulada_at = now(), anulada_por = v_uid, motivo_anulacion = trim(p_motivo)
   where id = p_venta_id;

  insert into public.auditoria (usuario_id, accion, entidad, entidad_id, datos)
  values (v_uid, 'ANULAR', 'ventas', p_venta_id::text,
          jsonb_build_object('numero', v_venta.numero, 'nota_credito', v_nc, 'motivo', trim(p_motivo)));

  return jsonb_build_object('nota_credito', v_nc, 'venta', v_venta.numero);
end $function$
;

CREATE OR REPLACE FUNCTION public.cfg(p_clave text, p_default text DEFAULT NULL::text)
 RETURNS text
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select coalesce((select valor from public.configuracion where clave = p_clave), p_default)
$function$
;

commit;

-- Comprobación (solo lectura)
select
  (select count(*) from information_schema.columns
    where table_schema = 'public' and table_name = 'productos' and column_name = 'tipo')        as col_tipo,
  (select count(*) from information_schema.columns
    where table_schema = 'public' and table_name = 'detalle_ventas' and column_name = 'es_servicio') as col_es_servicio,
  (select count(*) from public.productos where tipo = 'PRODUCTO')                               as productos,
  (select count(*) from pg_trigger where tgname = 'productos_servicio_sin_stock')                as trigger_ok,
  (select prosrc like '%v_servicio%' from pg_proc where proname = 'registrar_venta')            as venta_ok,
  (select prosrc like '%es_servicio%' from pg_proc where proname = 'anular_venta')              as anular_ok;
