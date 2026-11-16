-- Esquema de Servicios Autos LED · exportado el 15/11/2026 23:04 (hora de Venezuela)
-- Generado con supabase/exportar_esquema.sql. No contiene datos.

create sequence if not exists public.seq_compra as bigint increment by 1 minvalue 1 maxvalue 9223372036854775807 start with 1;

create sequence if not exists public.seq_documento_venta as bigint increment by 1 minvalue 1 maxvalue 9223372036854775807 start with 1;

create sequence if not exists public.seq_nota_credito as bigint increment by 1 minvalue 1 maxvalue 9223372036854775807 start with 1;

create table if not exists public._respaldo_detalle_ventas_v1 (
  id bigint,
  venta_id bigint,
  producto_id bigint,
  cantidad integer,
  precio_usd numeric(18,2),
  subtotal_usd numeric(18,2)
);

create table if not exists public._respaldo_movimientos_inventario_v1 (
  id bigint,
  producto_id bigint,
  tipo text,
  cantidad integer,
  costo_usd numeric(18,2),
  tasa_bcv numeric(18,4),
  equivalente_bs numeric(18,2),
  documento_origen text,
  usuario_id uuid,
  created_at timestamp with time zone
);

create table if not exists public._respaldo_reinicio_compras (
  id bigint,
  numero text,
  idempotency_key uuid,
  fecha timestamp with time zone,
  fecha_tasa date,
  tasa_bcv numeric(18,4),
  proveedor_id bigint,
  proveedor_rif text,
  proveedor_nombre text,
  factura_proveedor text,
  subtotal_usd numeric(14,2),
  iva_usd numeric(14,2),
  flete_usd numeric(14,2),
  otros_usd numeric(14,2),
  total_usd numeric(14,2),
  total_bs numeric(18,2),
  pagado_bs numeric(18,2),
  ajuste_redondeo_bs numeric(18,2),
  gastos_prorrateados boolean,
  metodo_costo text,
  estado text,
  observaciones text,
  usuario_id uuid,
  usuario_email text,
  anulada_at timestamp with time zone,
  anulada_por uuid,
  motivo_anulacion text
);

create table if not exists public._respaldo_reinicio_detalle_compras (
  id bigint,
  compra_id bigint,
  producto_id bigint,
  sku text,
  descripcion text,
  cantidad integer,
  costo_unitario_usd numeric(14,4),
  costo_real_usd numeric(14,4),
  subtotal_usd numeric(14,2),
  subtotal_bs numeric(18,2),
  tasa_bcv numeric(18,4),
  stock_anterior numeric(14,2),
  costo_anterior_usd numeric(14,4),
  costo_nuevo_usd numeric(14,4),
  precio_venta_anterior numeric(14,2),
  precio_venta_nuevo numeric(14,2)
);

create table if not exists public._respaldo_reinicio_detalle_ventas (
  id bigint,
  venta_id bigint,
  producto_id bigint,
  sku text,
  descripcion text,
  cantidad integer,
  precio_unitario_usd numeric(14,2),
  descuento_pct numeric(5,2),
  subtotal_usd numeric(14,2),
  exento_iva boolean,
  costo_unitario_usd numeric(14,4),
  tasa_bcv numeric(18,4),
  subtotal_bs numeric(18,2)
);

create table if not exists public._respaldo_reinicio_movimientos_inventario (
  id bigint,
  fecha timestamp with time zone,
  producto_id bigint,
  tipo text,
  motivo text,
  cantidad numeric(14,2),
  stock_anterior numeric(14,2),
  stock_nuevo numeric(14,2),
  costo_unitario_usd numeric(14,4),
  tasa_bcv numeric(18,4),
  costo_total_bs numeric(18,2),
  documento_tipo text,
  documento_id bigint,
  usuario_id uuid,
  observacion text
);

create table if not exists public._respaldo_reinicio_notas_credito (
  id bigint,
  numero text,
  venta_id bigint,
  fecha timestamp with time zone,
  tasa_bcv numeric(18,4),
  total_usd numeric(14,2),
  total_bs numeric(18,2),
  igtf_usd numeric(14,2),
  igtf_bs numeric(18,2),
  motivo text,
  usuario_id uuid
);

create table if not exists public._respaldo_reinicio_pagos_compra (
  id bigint,
  compra_id bigint,
  metodo text,
  moneda text,
  monto numeric(18,2),
  referencia text,
  created_at timestamp with time zone
);

create table if not exists public._respaldo_reinicio_pagos_venta (
  id bigint,
  venta_id bigint,
  metodo text,
  moneda text,
  monto numeric(18,2),
  referencia text,
  created_at timestamp with time zone
);

create table if not exists public._respaldo_reinicio_productos (
  id bigint,
  sku text,
  oem text,
  nombre text,
  categoria_id bigint,
  unidad_medida text,
  precio_usd numeric(18,2),
  costo_usd numeric(18,2),
  stock_minimo integer,
  activo boolean,
  created_at timestamp with time zone,
  marca text,
  stock_actual integer,
  codigo_barras text,
  subcategoria text,
  exento_iva boolean,
  updated_at timestamp with time zone
);

create table if not exists public._respaldo_reinicio_ventas (
  id bigint,
  numero text,
  idempotency_key uuid,
  fecha timestamp with time zone,
  fecha_tasa date,
  tasa_bcv numeric(18,4),
  cliente_id bigint,
  cliente_rif text,
  cliente_nombre text,
  exento_usd numeric(14,2),
  base_imponible_usd numeric(14,2),
  iva_porcentaje numeric(5,2),
  iva_usd numeric(14,2),
  total_usd numeric(14,2),
  exento_bs numeric(18,2),
  base_imponible_bs numeric(18,2),
  iva_bs numeric(18,2),
  total_bs numeric(18,2),
  pagado_divisas_usd numeric(14,2),
  igtf_porcentaje numeric(5,2),
  igtf_usd numeric(14,2),
  igtf_bs numeric(18,2),
  total_pagar_usd numeric(14,2),
  total_pagar_bs numeric(18,2),
  vuelto_usd numeric(14,2),
  vuelto_bs numeric(18,2),
  estado text,
  observaciones text,
  usuario_id uuid,
  usuario_email text,
  anulada_at timestamp with time zone,
  anulada_por uuid,
  motivo_anulacion text,
  aplica_iva boolean
);

create table if not exists public._respaldo_ventas_v1 (
  id bigint,
  numero_factura text,
  fecha timestamp with time zone,
  cliente_nombre text,
  cliente_rif text,
  tasa_bcv numeric(18,4),
  subtotal_usd numeric(18,2),
  iva_usd numeric(18,2),
  igtf_usd numeric(18,2),
  total_usd numeric(18,2),
  total_bs numeric(18,2),
  metodo_pago text,
  usuario_id uuid
);

create table if not exists public.auditoria (
  id bigint generated always as identity not null,
  fecha timestamp with time zone default now() not null,
  usuario_id uuid default auth.uid(),
  accion text not null,
  entidad text not null,
  entidad_id text,
  datos jsonb
);

create table if not exists public.categorias (
  id bigint generated by default as identity not null,
  nombre text not null,
  padre_id bigint
);

create table if not exists public.clientes (
  id bigint generated always as identity not null,
  rif text not null,
  nombre text not null,
  telefono text,
  email text,
  direccion text,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

create table if not exists public.compras (
  id bigint generated always as identity not null,
  numero text not null,
  idempotency_key uuid,
  fecha timestamp with time zone default now() not null,
  fecha_tasa date not null,
  tasa_bcv numeric(18,4) not null,
  proveedor_id bigint not null,
  proveedor_rif text not null,
  proveedor_nombre text not null,
  factura_proveedor text,
  subtotal_usd numeric(14,2) not null,
  iva_usd numeric(14,2) default 0 not null,
  flete_usd numeric(14,2) default 0 not null,
  otros_usd numeric(14,2) default 0 not null,
  total_usd numeric(14,2) not null,
  total_bs numeric(18,2) not null,
  pagado_bs numeric(18,2) default 0 not null,
  ajuste_redondeo_bs numeric(18,2) default 0 not null,
  gastos_prorrateados boolean default true not null,
  metodo_costo text default 'ULTIMO'::text not null,
  estado text default 'REGISTRADA'::text not null,
  observaciones text,
  usuario_id uuid,
  usuario_email text,
  anulada_at timestamp with time zone,
  anulada_por uuid,
  motivo_anulacion text
);

create table if not exists public.configuracion (
  clave text not null,
  valor text not null,
  descripcion text,
  updated_at timestamp with time zone default now()
);

create table if not exists public.detalle_compras (
  id bigint generated always as identity not null,
  compra_id bigint not null,
  producto_id bigint not null,
  sku text not null,
  descripcion text not null,
  cantidad integer not null,
  costo_unitario_usd numeric(14,4) not null,
  costo_real_usd numeric(14,4) not null,
  subtotal_usd numeric(14,2) not null,
  subtotal_bs numeric(18,2) not null,
  tasa_bcv numeric(18,4) not null,
  stock_anterior numeric(14,2) not null,
  costo_anterior_usd numeric(14,4) default 0 not null,
  costo_nuevo_usd numeric(14,4) not null,
  precio_venta_anterior numeric(14,2),
  precio_venta_nuevo numeric(14,2)
);

create table if not exists public.detalle_ventas (
  id bigint generated always as identity not null,
  venta_id bigint not null,
  producto_id bigint not null,
  sku text not null,
  descripcion text not null,
  cantidad integer not null,
  precio_unitario_usd numeric(14,2) not null,
  descuento_pct numeric(5,2) default 0 not null,
  subtotal_usd numeric(14,2) not null,
  exento_iva boolean default false not null,
  costo_unitario_usd numeric(14,4) default 0 not null,
  tasa_bcv numeric(18,4) not null,
  subtotal_bs numeric(18,2) not null
);

create table if not exists public.movimientos_inventario (
  id bigint generated always as identity not null,
  fecha timestamp with time zone default now() not null,
  producto_id bigint not null,
  tipo text not null,
  motivo text not null,
  cantidad numeric(14,2) not null,
  stock_anterior numeric(14,2) not null,
  stock_nuevo numeric(14,2) not null,
  costo_unitario_usd numeric(14,4) default 0 not null,
  tasa_bcv numeric(18,4),
  costo_total_bs numeric(18,2),
  documento_tipo text,
  documento_id bigint,
  usuario_id uuid,
  observacion text
);

create table if not exists public.notas_credito (
  id bigint generated always as identity not null,
  numero text not null,
  venta_id bigint not null,
  fecha timestamp with time zone default now() not null,
  tasa_bcv numeric(18,4) not null,
  total_usd numeric(14,2) not null,
  total_bs numeric(18,2) not null,
  igtf_usd numeric(14,2) default 0 not null,
  igtf_bs numeric(18,2) default 0 not null,
  motivo text not null,
  usuario_id uuid
);

create table if not exists public.pagos_compra (
  id bigint generated always as identity not null,
  compra_id bigint not null,
  metodo text not null,
  moneda text not null,
  monto numeric(18,2) not null,
  referencia text,
  created_at timestamp with time zone default now()
);

create table if not exists public.pagos_venta (
  id bigint generated always as identity not null,
  venta_id bigint not null,
  metodo text not null,
  moneda text not null,
  monto numeric(18,2) not null,
  referencia text,
  created_at timestamp with time zone default now()
);

create table if not exists public.productos (
  id bigint generated by default as identity not null,
  sku text not null,
  oem text,
  nombre text not null,
  categoria_id bigint,
  unidad_medida text default 'Pieza'::text,
  precio_usd numeric(18,2) not null,
  costo_usd numeric(18,2) not null,
  stock_minimo integer default 5,
  activo boolean default true,
  created_at timestamp with time zone default timezone('utc'::text, now()),
  marca text,
  stock_actual integer default 0,
  codigo_barras text,
  subcategoria text,
  exento_iva boolean default false not null,
  updated_at timestamp with time zone default now()
);

create table if not exists public.proveedores (
  id bigint generated always as identity not null,
  rif text not null,
  nombre text not null,
  tipo text default 'LOCAL'::text not null,
  contacto text,
  telefono text,
  email text,
  direccion text,
  notas text,
  activo boolean default true not null,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

create table if not exists public.tasas_bcv (
  id bigint generated by default as identity not null,
  fecha date not null,
  tasa numeric(18,4) not null,
  fuente text default 'API/Scraping'::text,
  usuario_id uuid,
  created_at timestamp with time zone default timezone('utc'::text, now())
);

create table if not exists public.usuarios (
  id uuid not null,
  nombre text not null,
  email text not null,
  rol text default 'Ventas'::text,
  activo boolean default true,
  created_at timestamp with time zone default timezone('utc'::text, now())
);

create table if not exists public.ventas (
  id bigint generated always as identity not null,
  numero text not null,
  idempotency_key uuid,
  fecha timestamp with time zone default now() not null,
  fecha_tasa date not null,
  tasa_bcv numeric(18,4) not null,
  cliente_id bigint,
  cliente_rif text not null,
  cliente_nombre text not null,
  exento_usd numeric(14,2) default 0 not null,
  base_imponible_usd numeric(14,2) default 0 not null,
  iva_porcentaje numeric(5,2) not null,
  iva_usd numeric(14,2) default 0 not null,
  total_usd numeric(14,2) not null,
  exento_bs numeric(18,2) default 0 not null,
  base_imponible_bs numeric(18,2) default 0 not null,
  iva_bs numeric(18,2) default 0 not null,
  total_bs numeric(18,2) not null,
  pagado_divisas_usd numeric(14,2) default 0 not null,
  igtf_porcentaje numeric(5,2) default 0 not null,
  igtf_usd numeric(14,2) default 0 not null,
  igtf_bs numeric(18,2) default 0 not null,
  total_pagar_usd numeric(14,2) not null,
  total_pagar_bs numeric(18,2) not null,
  vuelto_usd numeric(14,2) default 0 not null,
  vuelto_bs numeric(18,2) default 0 not null,
  estado text default 'EMITIDA'::text not null,
  observaciones text,
  usuario_id uuid,
  usuario_email text,
  anulada_at timestamp with time zone,
  anulada_por uuid,
  motivo_anulacion text,
  aplica_iva boolean default true not null
);

alter table public.auditoria add constraint auditoria_pkey PRIMARY KEY (id);

alter table public.categorias add constraint categorias_pkey PRIMARY KEY (id);

alter table public.clientes add constraint clientes_pkey PRIMARY KEY (id);

alter table public.clientes add constraint clientes_rif_key UNIQUE (rif);

alter table public.compras add constraint compras_estado_check CHECK ((estado = ANY (ARRAY['REGISTRADA'::text, 'ANULADA'::text])));

alter table public.compras add constraint compras_idempotency_key_key UNIQUE (idempotency_key);

alter table public.compras add constraint compras_numero_key UNIQUE (numero);

alter table public.compras add constraint compras_pkey PRIMARY KEY (id);

alter table public.compras add constraint compras_tasa_bcv_check CHECK ((tasa_bcv > (0)::numeric));

alter table public.configuracion add constraint configuracion_pkey PRIMARY KEY (clave);

alter table public.detalle_compras add constraint detalle_compras_cantidad_check CHECK ((cantidad > 0));

alter table public.detalle_compras add constraint detalle_compras_pkey PRIMARY KEY (id);

alter table public.detalle_ventas add constraint detalle_ventas_cantidad_check CHECK ((cantidad > 0));

alter table public.detalle_ventas add constraint detalle_ventas_pkey PRIMARY KEY (id);

alter table public.movimientos_inventario add constraint movimientos_inventario_cantidad_check CHECK ((cantidad > (0)::numeric));

alter table public.movimientos_inventario add constraint movimientos_inventario_pkey PRIMARY KEY (id);

alter table public.movimientos_inventario add constraint movimientos_inventario_tipo_check CHECK ((tipo = ANY (ARRAY['ENTRADA'::text, 'SALIDA'::text])));

alter table public.notas_credito add constraint notas_credito_numero_key UNIQUE (numero);

alter table public.notas_credito add constraint notas_credito_pkey PRIMARY KEY (id);

alter table public.pagos_compra add constraint pagos_compra_moneda_check CHECK ((moneda = ANY (ARRAY['USD'::text, 'VES'::text])));

alter table public.pagos_compra add constraint pagos_compra_monto_check CHECK ((monto > (0)::numeric));

alter table public.pagos_compra add constraint pagos_compra_pkey PRIMARY KEY (id);

alter table public.pagos_venta add constraint pagos_venta_moneda_check CHECK ((moneda = ANY (ARRAY['USD'::text, 'VES'::text])));

alter table public.pagos_venta add constraint pagos_venta_monto_check CHECK ((monto > (0)::numeric));

alter table public.pagos_venta add constraint pagos_venta_pkey PRIMARY KEY (id);

alter table public.productos add constraint productos_pkey PRIMARY KEY (id);

alter table public.productos add constraint productos_sku_key UNIQUE (sku);

alter table public.proveedores add constraint proveedores_pkey PRIMARY KEY (id);

alter table public.proveedores add constraint proveedores_rif_key UNIQUE (rif);

alter table public.tasas_bcv add constraint tasas_bcv_fecha_key UNIQUE (fecha);

alter table public.tasas_bcv add constraint tasas_bcv_pkey PRIMARY KEY (id);

alter table public.usuarios add constraint usuarios_email_key UNIQUE (email);

alter table public.usuarios add constraint usuarios_pkey PRIMARY KEY (id);

alter table public.usuarios add constraint usuarios_rol_check CHECK ((rol = ANY (ARRAY['Administrador'::text, 'Inventario'::text, 'Compras'::text, 'Ventas'::text, 'Caja'::text, 'Auditor'::text])));

alter table public.ventas add constraint ventas_estado_check CHECK ((estado = ANY (ARRAY['EMITIDA'::text, 'ANULADA'::text])));

alter table public.ventas add constraint ventas_idempotency_key_key UNIQUE (idempotency_key);

alter table public.ventas add constraint ventas_numero_key UNIQUE (numero);

alter table public.ventas add constraint ventas_pkey PRIMARY KEY (id);

alter table public.ventas add constraint ventas_tasa_bcv_check CHECK ((tasa_bcv > (0)::numeric));

alter table public.categorias add constraint categorias_padre_id_fkey FOREIGN KEY (padre_id) REFERENCES categorias(id);

alter table public.compras add constraint compras_proveedor_id_fkey FOREIGN KEY (proveedor_id) REFERENCES proveedores(id);

alter table public.detalle_compras add constraint detalle_compras_compra_id_fkey FOREIGN KEY (compra_id) REFERENCES compras(id) ON DELETE RESTRICT;

alter table public.detalle_compras add constraint detalle_compras_producto_id_fkey FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE RESTRICT;

alter table public.detalle_ventas add constraint detalle_ventas_producto_id_fkey FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE RESTRICT;

alter table public.detalle_ventas add constraint detalle_ventas_venta_id_fkey FOREIGN KEY (venta_id) REFERENCES ventas(id) ON DELETE RESTRICT;

alter table public.movimientos_inventario add constraint movimientos_inventario_producto_id_fkey FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE RESTRICT;

alter table public.notas_credito add constraint notas_credito_venta_id_fkey FOREIGN KEY (venta_id) REFERENCES ventas(id);

alter table public.pagos_compra add constraint pagos_compra_compra_id_fkey FOREIGN KEY (compra_id) REFERENCES compras(id) ON DELETE RESTRICT;

alter table public.pagos_venta add constraint pagos_venta_venta_id_fkey FOREIGN KEY (venta_id) REFERENCES ventas(id) ON DELETE RESTRICT;

alter table public.productos add constraint productos_categoria_id_fkey FOREIGN KEY (categoria_id) REFERENCES categorias(id);

alter table public.usuarios add constraint usuarios_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE;

alter table public.ventas add constraint ventas_cliente_id_fkey FOREIGN KEY (cliente_id) REFERENCES clientes(id);

CREATE INDEX compras_fecha_idx ON public.compras USING btree (fecha DESC);

CREATE INDEX compras_proveedor_idx ON public.compras USING btree (proveedor_id);

CREATE INDEX detalle_compras_compra_idx ON public.detalle_compras USING btree (compra_id);

CREATE INDEX detalle_compras_producto_idx ON public.detalle_compras USING btree (producto_id);

CREATE INDEX detalle_ventas_venta_idx ON public.detalle_ventas USING btree (venta_id);

CREATE INDEX mov_inv_producto_idx ON public.movimientos_inventario USING btree (producto_id, fecha DESC);

CREATE INDEX pagos_compra_compra_idx ON public.pagos_compra USING btree (compra_id);

CREATE INDEX pagos_venta_venta_idx ON public.pagos_venta USING btree (venta_id);

CREATE UNIQUE INDEX tasas_bcv_fecha_uk ON public.tasas_bcv USING btree (fecha);

CREATE INDEX ventas_fecha_idx ON public.ventas USING btree (fecha DESC);

CREATE OR REPLACE FUNCTION public.anular_compra(p_compra_id bigint, p_motivo text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_uid       uuid := auth.uid();
  v_email     text := lower(coalesce(auth.jwt() ->> 'email', ''));
  v_admins    text := lower(replace(public.cfg('emails_administradores', ''), ' ', ''));
  v_sin_stock boolean := public.cfg('permitir_venta_sin_stock', 'false')::boolean;
  v_compra    public.compras%rowtype;
  v_det       record;
  v_prod      record;
  v_stock     numeric;
begin
  if v_uid is null then
    raise exception 'Sesión no válida.';
  end if;
  if v_admins <> '' and not (v_email = any (string_to_array(v_admins, ','))) then
    raise exception 'Solo un administrador puede anular compras.';
  end if;
  if length(trim(coalesce(p_motivo, ''))) < 10 then
    raise exception 'Indica un motivo de al menos 10 caracteres.';
  end if;

  select * into v_compra from public.compras where id = p_compra_id for update;
  if not found then
    raise exception 'La compra no existe.';
  end if;
  if v_compra.estado = 'ANULADA' then
    raise exception 'La compra % ya está anulada.', v_compra.numero;
  end if;

  perform set_config('app.origen_stock', 'rpc', true);

  for v_det in select * from public.detalle_compras where compra_id = p_compra_id order by producto_id loop
    select * into v_prod from public.productos where id = v_det.producto_id for update;
    v_stock := coalesce(v_prod.stock_actual, 0);
    if not v_sin_stock and v_stock < v_det.cantidad then
      raise exception 'No se puede anular: de % quedan % und y la compra ingresó %. Parte ya se vendió.',
        v_det.sku, v_stock, v_det.cantidad;
    end if;

    update public.productos
       set stock_actual = coalesce(stock_actual, 0) - v_det.cantidad,
           costo_usd  = case when round(coalesce(costo_usd, 0)::numeric, 4) = round(v_det.costo_nuevo_usd, 4)
                             then v_det.costo_anterior_usd else costo_usd end,
           precio_usd = case when v_det.precio_venta_nuevo is not null
                              and round(coalesce(precio_usd, 0)::numeric, 2) = v_det.precio_venta_nuevo
                             then v_det.precio_venta_anterior else precio_usd end,
           updated_at = now()
     where id = v_det.producto_id;

    insert into public.movimientos_inventario (
      producto_id, tipo, motivo, cantidad, stock_anterior, stock_nuevo, costo_unitario_usd,
      tasa_bcv, costo_total_bs, documento_tipo, documento_id, usuario_id, observacion)
    values (
      v_det.producto_id, 'SALIDA', 'ANULACION_COMPRA', v_det.cantidad, v_stock, v_stock - v_det.cantidad,
      v_det.costo_real_usd, v_compra.tasa_bcv,
      round(v_det.cantidad * v_det.costo_real_usd * v_compra.tasa_bcv, 2),
      'COMPRA', p_compra_id, v_uid, 'Anula ' || v_compra.numero);
  end loop;

  update public.compras
     set estado = 'ANULADA', anulada_at = now(), anulada_por = v_uid, motivo_anulacion = trim(p_motivo)
   where id = p_compra_id;

  insert into public.auditoria (usuario_id, accion, entidad, entidad_id, datos)
  values (v_uid, 'ANULAR', 'compras', p_compra_id::text,
          jsonb_build_object('numero', v_compra.numero, 'motivo', trim(p_motivo)));

  return jsonb_build_object('compra', v_compra.numero);
end $function$
;

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

CREATE OR REPLACE FUNCTION public.es_admin()
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select auth.uid() is not null and (
    replace(coalesce(public.cfg('emails_administradores', ''), ''), ' ', '') = ''
    or lower(coalesce(auth.jwt() ->> 'email', '')) = any (
         string_to_array(lower(replace(public.cfg('emails_administradores', ''), ' ', '')), ','))
  )
$function$
;

CREATE OR REPLACE FUNCTION public.fecha_vzla()
 RETURNS date
 LANGUAGE sql
 STABLE
AS $function$
  select (now() at time zone 'America/Caracas')::date
$function$
;

CREATE OR REPLACE FUNCTION public.registrar_compra(p_proveedor_id bigint, p_items jsonb, p_pagos jsonb DEFAULT '[]'::jsonb, p_flete_usd numeric DEFAULT 0, p_otros_usd numeric DEFAULT 0, p_iva_usd numeric DEFAULT 0, p_factura_proveedor text DEFAULT NULL::text, p_observaciones text DEFAULT NULL::text, p_idempotency_key uuid DEFAULT NULL::uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_uid        uuid    := auth.uid();
  v_email      text    := coalesce(auth.jwt() ->> 'email', '');
  v_dias_max   int     := public.cfg('tasa_dias_max', '4')::int;
  v_metodo     text    := upper(public.cfg('metodo_costo', 'ULTIMO'));
  v_prorratear boolean := public.cfg('prorratear_gastos', 'true')::boolean;
  v_flete      numeric := round(coalesce(p_flete_usd, 0), 2);
  v_otros      numeric := round(coalesce(p_otros_usd, 0), 2);
  v_iva        numeric := round(coalesce(p_iva_usd, 0), 2);
  v_fecha_tasa date;
  v_tasa       numeric;
  v_prov       record;
  v_existe     record;
  v_item       record;
  v_prod       record;
  v_linea      jsonb;
  v_lineas     jsonb   := '[]'::jsonb;
  v_subtotal   numeric := 0;
  v_factor     numeric := 1;
  v_total_usd  numeric;
  v_total_bs   numeric;
  v_ves        numeric;
  v_usd        numeric;
  v_pagado_bs  numeric;
  v_cant       numeric;
  v_stock      numeric;
  v_costo_ant  numeric;
  v_costo_real numeric;
  v_costo_new  numeric;
  v_compra_id  bigint;
  v_numero     text;
begin
  if v_uid is null then
    raise exception 'Sesión no válida. Cierra sesión e ingresa de nuevo.';
  end if;

  if p_idempotency_key is not null then
    select id, numero into v_existe from public.compras where idempotency_key = p_idempotency_key;
    if found then
      return jsonb_build_object('compra_id', v_existe.id, 'numero', v_existe.numero, 'repetida', true);
    end if;
  end if;

  if p_items is null or jsonb_typeof(p_items) <> 'array' or jsonb_array_length(p_items) = 0 then
    raise exception 'La compra no tiene productos.';
  end if;
  if v_flete < 0 or v_otros < 0 or v_iva < 0 then
    raise exception 'Flete, otros gastos e IVA no pueden ser negativos.';
  end if;
  if exists (select 1 from jsonb_array_elements(p_items) e
             where coalesce((e ->> 'costo_usd')::numeric, -1) < 0) then
    raise exception 'Hay un producto con costo inválido.';
  end if;
  p_pagos := coalesce(p_pagos, '[]'::jsonb);

  select tv.fecha_tasa, tv.tasa into v_fecha_tasa, v_tasa from public.tasa_vigente() tv;
  if v_tasa is null then
    raise exception 'No hay tasa BCV registrada. Regístrala en el módulo Tasa BCV.';
  end if;
  if public.fecha_vzla() - v_fecha_tasa > v_dias_max then
    raise exception 'La última tasa BCV es del %. Actualízala antes de registrar compras.',
      to_char(v_fecha_tasa, 'DD/MM/YYYY');
  end if;

  select * into v_prov from public.proveedores where id = p_proveedor_id;
  if not found then
    raise exception 'Selecciona un proveedor válido.';
  end if;
  if not v_prov.activo then
    raise exception 'El proveedor % está inactivo.', v_prov.nombre;
  end if;

  -- 1ª pasada: agrupar por producto y validar
  for v_item in
    select (e ->> 'producto_id')::bigint                                   as producto_id,
           sum((e ->> 'cantidad')::numeric)                                as cantidad,
           sum((e ->> 'cantidad')::numeric * (e ->> 'costo_usd')::numeric) as importe,
           max(nullif(e ->> 'precio_venta_usd', '')::numeric)              as precio_venta
    from jsonb_array_elements(p_items) e
    group by 1
    order by 1
  loop
    if v_item.cantidad is null or v_item.cantidad <= 0 or v_item.cantidad <> trunc(v_item.cantidad) then
      raise exception 'Cantidad inválida para el producto %.', v_item.producto_id;
    end if;
    if v_item.precio_venta is not null and v_item.precio_venta <= 0 then
      raise exception 'El nuevo precio de venta debe ser mayor que cero.';
    end if;
    v_lineas := v_lineas || jsonb_build_object(
      'producto_id', v_item.producto_id, 'cantidad', v_item.cantidad,
      'costo', round(v_item.importe / v_item.cantidad, 4),
      'subtotal', round(v_item.importe, 2), 'precio_venta', v_item.precio_venta);
    v_subtotal := v_subtotal + round(v_item.importe, 2);
  end loop;

  if v_prorratear and v_subtotal > 0 then
    v_factor := 1 + (v_flete + v_otros) / v_subtotal;
  end if;
  v_total_usd := v_subtotal + v_iva + v_flete + v_otros;
  v_total_bs  := round(v_total_usd * v_tasa, 2);

  -- Pago inmediato (contado)
  if exists (select 1 from jsonb_array_elements(p_pagos) e
             where coalesce((e ->> 'monto')::numeric, 0) <= 0
                or coalesce(e ->> 'moneda', '') not in ('USD', 'VES')) then
    raise exception 'Hay un pago con monto o moneda inválidos.';
  end if;
  select coalesce(sum((e ->> 'monto')::numeric) filter (where e ->> 'moneda' = 'VES'), 0),
         coalesce(sum((e ->> 'monto')::numeric) filter (where e ->> 'moneda' = 'USD'), 0)
    into v_ves, v_usd
  from jsonb_array_elements(p_pagos) e;
  v_pagado_bs := v_ves + round(v_usd * v_tasa, 2);
  if v_pagado_bs + 0.009 < v_total_bs then
    raise exception 'Pago incompleto: faltan Bs. %. Las compras son de contado.',
      to_char(v_total_bs - v_pagado_bs, 'FM999999990.00');
  end if;

  perform set_config('app.origen_stock', 'rpc', true);
  v_numero := 'CP-' || lpad(nextval('public.seq_compra')::text, 8, '0');

  insert into public.compras (
    numero, idempotency_key, fecha_tasa, tasa_bcv, proveedor_id, proveedor_rif, proveedor_nombre,
    factura_proveedor, subtotal_usd, iva_usd, flete_usd, otros_usd, total_usd, total_bs,
    pagado_bs, ajuste_redondeo_bs, gastos_prorrateados, metodo_costo, observaciones, usuario_id, usuario_email)
  values (
    v_numero, p_idempotency_key, v_fecha_tasa, v_tasa, v_prov.id, v_prov.rif, v_prov.nombre,
    nullif(trim(coalesce(p_factura_proveedor, '')), ''), v_subtotal, v_iva, v_flete, v_otros,
    v_total_usd, v_total_bs, v_pagado_bs, greatest(v_pagado_bs - v_total_bs, 0), v_prorratear,
    v_metodo, nullif(trim(coalesce(p_observaciones, '')), ''), v_uid, v_email)
  returning id into v_compra_id;

  -- 2ª pasada: stock, costo, precio, detalle y kardex
  for v_linea in select value from jsonb_array_elements(v_lineas) loop
    select * into v_prod from public.productos where id = (v_linea ->> 'producto_id')::bigint for update;
    if not found then
      raise exception 'El producto % ya no existe.', v_linea ->> 'producto_id';
    end if;

    v_cant       := (v_linea ->> 'cantidad')::numeric;
    v_stock      := coalesce(v_prod.stock_actual, 0);
    v_costo_ant  := coalesce(v_prod.costo_usd, 0)::numeric;
    v_costo_real := round((v_linea ->> 'costo')::numeric * v_factor, 4);
    if v_metodo = 'PROMEDIO' and v_stock > 0 then
      v_costo_new := round((v_stock * v_costo_ant + v_cant * v_costo_real) / (v_stock + v_cant), 4);
    else
      v_costo_new := v_costo_real;
    end if;

    update public.productos
       set stock_actual = coalesce(stock_actual, 0) + v_cant,
           costo_usd    = v_costo_new,
           precio_usd   = coalesce((v_linea ->> 'precio_venta')::numeric, precio_usd),
           updated_at   = now()
     where id = v_prod.id;

    insert into public.detalle_compras (
      compra_id, producto_id, sku, descripcion, cantidad, costo_unitario_usd, costo_real_usd,
      subtotal_usd, subtotal_bs, tasa_bcv, stock_anterior, costo_anterior_usd, costo_nuevo_usd,
      precio_venta_anterior, precio_venta_nuevo)
    values (
      v_compra_id, v_prod.id, v_prod.sku, v_prod.nombre, v_cant::int, (v_linea ->> 'costo')::numeric,
      v_costo_real, (v_linea ->> 'subtotal')::numeric,
      round((v_linea ->> 'subtotal')::numeric * v_tasa, 2), v_tasa, v_stock, v_costo_ant, v_costo_new,
      round(coalesce(v_prod.precio_usd, 0)::numeric, 2), (v_linea ->> 'precio_venta')::numeric);

    insert into public.movimientos_inventario (
      producto_id, tipo, motivo, cantidad, stock_anterior, stock_nuevo, costo_unitario_usd,
      tasa_bcv, costo_total_bs, documento_tipo, documento_id, usuario_id, observacion)
    values (
      v_prod.id, 'ENTRADA', 'COMPRA', v_cant, v_stock, v_stock + v_cant, v_costo_real, v_tasa,
      round(v_cant * v_costo_real * v_tasa, 2), 'COMPRA', v_compra_id, v_uid,
      v_numero || ' · ' || v_prov.nombre);
  end loop;

  insert into public.pagos_compra (compra_id, metodo, moneda, monto, referencia)
  select v_compra_id, coalesce(nullif(e ->> 'metodo', ''), 'N/D'), e ->> 'moneda',
         round((e ->> 'monto')::numeric, 2), nullif(trim(coalesce(e ->> 'referencia', '')), '')
  from jsonb_array_elements(p_pagos) e;

  insert into public.auditoria (usuario_id, accion, entidad, entidad_id, datos)
  values (v_uid, 'CREAR', 'compras', v_compra_id::text,
          jsonb_build_object('numero', v_numero, 'proveedor', v_prov.nombre,
                             'total_usd', v_total_usd, 'total_bs', v_total_bs, 'tasa', v_tasa));

  return jsonb_build_object('compra_id', v_compra_id, 'numero', v_numero, 'repetida', false,
                            'total_usd', v_total_usd, 'total_bs', v_total_bs);
end $function$
;

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
  for v_item in
    select (e ->> 'producto_id')::bigint                     as producto_id,
           sum((e ->> 'cantidad')::numeric)                  as cantidad,
           max(coalesce((e ->> 'descuento_pct')::numeric, 0)) as descuento_pct
    from jsonb_array_elements(p_items) e
    group by 1
    order by 1
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
    if coalesce(v_prod.precio_usd, 0) <= 0 then
      raise exception 'El producto % no tiene precio de venta.', v_prod.sku;
    end if;
    if not v_sin_stock and coalesce(v_prod.stock_actual, 0) < v_item.cantidad then
      raise exception 'Stock insuficiente para % (%): disponible %, solicitado %.',
        v_prod.sku, v_prod.nombre, coalesce(v_prod.stock_actual, 0), v_item.cantidad;
    end if;

    v_sub := round(v_prod.precio_usd::numeric * v_item.cantidad * (1 - v_item.descuento_pct / 100), 2);
    if coalesce(v_prod.exento_iva, false) then
      v_exento_usd := v_exento_usd + v_sub;
    else
      v_base_usd := v_base_usd + v_sub;
    end if;

    v_lineas := v_lineas || jsonb_build_object(
      'producto_id', v_prod.id, 'sku', v_prod.sku, 'descripcion', v_prod.nombre,
      'cantidad', v_item.cantidad, 'precio', round(v_prod.precio_usd::numeric, 2),
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
      subtotal_usd, exento_iva, costo_unitario_usd, tasa_bcv, subtotal_bs)
    values (
      v_venta_id, (v_linea ->> 'producto_id')::bigint, v_linea ->> 'sku', v_linea ->> 'descripcion',
      v_cant::int, (v_linea ->> 'precio')::numeric, (v_linea ->> 'descuento')::numeric,
      (v_linea ->> 'subtotal')::numeric, (v_linea ->> 'exento')::boolean,
      (v_linea ->> 'costo')::numeric, v_tasa, round((v_linea ->> 'subtotal')::numeric * v_tasa, 2));

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

CREATE OR REPLACE FUNCTION public.trg_productos_auditoria()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
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
end $function$
;

CREATE OR REPLACE FUNCTION public.trg_productos_kardex()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_diff numeric;
  v_tasa numeric;
begin
  -- Las funciones del POS escriben su propio kardex
  if coalesce(current_setting('app.origen_stock', true), '') = 'rpc' then
    return new;
  end if;

  select tv.tasa into v_tasa from public.tasa_vigente() tv;

  if tg_op = 'INSERT' then
    if coalesce(new.stock_actual, 0) > 0 then
      insert into public.movimientos_inventario
        (producto_id, tipo, motivo, cantidad, stock_anterior, stock_nuevo, costo_unitario_usd,
         tasa_bcv, costo_total_bs, documento_tipo, documento_id, usuario_id, observacion)
      values
        (new.id, 'ENTRADA', 'INVENTARIO_INICIAL', new.stock_actual, 0, new.stock_actual,
         coalesce(new.costo_usd, 0), v_tasa,
         round(new.stock_actual * coalesce(new.costo_usd, 0) * coalesce(v_tasa, 0), 2),
         'PRODUCTO', new.id, auth.uid(), 'Stock inicial al crear el producto');
    end if;
  elsif coalesce(new.stock_actual, 0) <> coalesce(old.stock_actual, 0) then
    v_diff := coalesce(new.stock_actual, 0) - coalesce(old.stock_actual, 0);
    insert into public.movimientos_inventario
      (producto_id, tipo, motivo, cantidad, stock_anterior, stock_nuevo, costo_unitario_usd,
       tasa_bcv, costo_total_bs, documento_tipo, documento_id, usuario_id, observacion)
    values
      (new.id, case when v_diff > 0 then 'ENTRADA' else 'SALIDA' end, 'AJUSTE_MANUAL',
       abs(v_diff), coalesce(old.stock_actual, 0), coalesce(new.stock_actual, 0),
       coalesce(new.costo_usd, 0), v_tasa,
       round(abs(v_diff) * coalesce(new.costo_usd, 0) * coalesce(v_tasa, 0), 2),
       'PRODUCTO', new.id, auth.uid(), 'Ajuste por edición directa del producto');
  end if;
  return new;
end $function$
;

CREATE OR REPLACE FUNCTION public.trg_tasas_auditoria()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
begin
  insert into public.auditoria (accion, entidad, entidad_id, datos)
  values (tg_op, 'tasas_bcv', new.fecha::text,
          jsonb_build_object('anterior', case when tg_op = 'UPDATE' then to_jsonb(old) end,
                             'nuevo', to_jsonb(new)));
  return new;
end $function$
;

CREATE TRIGGER productos_auditoria AFTER DELETE OR UPDATE OF precio_usd, costo_usd ON public.productos FOR EACH ROW EXECUTE FUNCTION trg_productos_auditoria();

CREATE TRIGGER productos_kardex AFTER INSERT OR UPDATE OF stock_actual ON public.productos FOR EACH ROW EXECUTE FUNCTION trg_productos_kardex();

CREATE TRIGGER tasas_auditoria AFTER INSERT OR UPDATE ON public.tasas_bcv FOR EACH ROW EXECUTE FUNCTION trg_tasas_auditoria();

alter table public._respaldo_detalle_ventas_v1 enable row level security;

alter table public._respaldo_movimientos_inventario_v1 enable row level security;

alter table public._respaldo_reinicio_compras enable row level security;

alter table public._respaldo_reinicio_detalle_compras enable row level security;

alter table public._respaldo_reinicio_detalle_ventas enable row level security;

alter table public._respaldo_reinicio_movimientos_inventario enable row level security;

alter table public._respaldo_reinicio_notas_credito enable row level security;

alter table public._respaldo_reinicio_pagos_compra enable row level security;

alter table public._respaldo_reinicio_pagos_venta enable row level security;

alter table public._respaldo_reinicio_productos enable row level security;

alter table public._respaldo_reinicio_ventas enable row level security;

alter table public._respaldo_ventas_v1 enable row level security;

alter table public.auditoria enable row level security;

alter table public.categorias enable row level security;

alter table public.clientes enable row level security;

alter table public.compras enable row level security;

alter table public.configuracion enable row level security;

alter table public.detalle_compras enable row level security;

alter table public.detalle_ventas enable row level security;

alter table public.movimientos_inventario enable row level security;

alter table public.notas_credito enable row level security;

alter table public.pagos_compra enable row level security;

alter table public.pagos_venta enable row level security;

alter table public.productos enable row level security;

alter table public.proveedores enable row level security;

alter table public.tasas_bcv enable row level security;

alter table public.usuarios enable row level security;

alter table public.ventas enable row level security;

create policy autenticados_lectura on public.auditoria as permissive for select to authenticated
  using (true);

create policy admin_borrar on public.categorias as permissive for delete to authenticated
  using (es_admin());

create policy autenticados_crear on public.categorias as permissive for insert to authenticated
  with check (true);

create policy autenticados_editar on public.categorias as permissive for update to authenticated
  using (true)
  with check (true);

create policy autenticados_lectura on public.categorias as permissive for select to authenticated
  using (true);

create policy admin_borrar on public.clientes as permissive for delete to authenticated
  using (es_admin());

create policy autenticados_crear on public.clientes as permissive for insert to authenticated
  with check (true);

create policy autenticados_editar on public.clientes as permissive for update to authenticated
  using (true)
  with check (true);

create policy autenticados_lectura on public.clientes as permissive for select to authenticated
  using (true);

create policy autenticados_lectura on public.compras as permissive for select to authenticated
  using (true);

create policy admin_escritura on public.configuracion as permissive for all to authenticated
  using (es_admin())
  with check (es_admin());

create policy autenticados_lectura on public.configuracion as permissive for select to authenticated
  using (true);

create policy autenticados_lectura on public.detalle_compras as permissive for select to authenticated
  using (true);

create policy autenticados_lectura on public.detalle_ventas as permissive for select to authenticated
  using (true);

create policy autenticados_lectura on public.movimientos_inventario as permissive for select to authenticated
  using (true);

create policy autenticados_lectura on public.notas_credito as permissive for select to authenticated
  using (true);

create policy autenticados_lectura on public.pagos_compra as permissive for select to authenticated
  using (true);

create policy autenticados_lectura on public.pagos_venta as permissive for select to authenticated
  using (true);

create policy admin_borrar on public.productos as permissive for delete to authenticated
  using (es_admin());

create policy autenticados_crear on public.productos as permissive for insert to authenticated
  with check (true);

create policy autenticados_editar on public.productos as permissive for update to authenticated
  using (true)
  with check (true);

create policy autenticados_lectura on public.productos as permissive for select to authenticated
  using (true);

create policy admin_borrar on public.proveedores as permissive for delete to authenticated
  using (es_admin());

create policy autenticados_crear on public.proveedores as permissive for insert to authenticated
  with check (true);

create policy autenticados_editar on public.proveedores as permissive for update to authenticated
  using (true)
  with check (true);

create policy autenticados_lectura on public.proveedores as permissive for select to authenticated
  using (true);

create policy admin_borrar on public.tasas_bcv as permissive for delete to authenticated
  using (es_admin());

create policy autenticados_crear on public.tasas_bcv as permissive for insert to authenticated
  with check (true);

create policy autenticados_editar on public.tasas_bcv as permissive for update to authenticated
  using (true)
  with check (true);

create policy autenticados_lectura on public.tasas_bcv as permissive for select to authenticated
  using (true);

create policy admin_escritura on public.usuarios as permissive for all to authenticated
  using (es_admin())
  with check (es_admin());

create policy ver_propio_o_admin on public.usuarios as permissive for select to authenticated
  using (((id = auth.uid()) OR es_admin()));

create policy autenticados_lectura on public.ventas as permissive for select to authenticated
  using (true);
