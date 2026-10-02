"""
COMPRAS DE CONTADO · Fase 5
=============================
Flujo en 3 pasos:
  1) Elegir proveedor
  2) Agregar productos (cantidad + costo USD, opcional nuevo precio de venta)
  3) Pagar en el acto (Bs a tasa BCV del día) y registrar

registrar_compra (SQL) hace todo de una vez: suma stock, actualiza costo,
escribe kardex y guarda los pagos. Sin cuentas por pagar.
"""
import uuid
from datetime import timedelta

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from app.db import supabase
from app import utils as U
from app.comprobante import cargar_compra, generar_html_compra
from app.modules.ventas import CSS, METODOS, _pasos
from app.modules.proveedores import dialog_proveedor, obtener_proveedores
from app.modules.productos import generar_sku, obtener_categorias

COLS = "id, sku, nombre, marca, precio_usd, costo_usd, stock_actual, activo, categoria_id"


# =====================================================================
# ESTADO
# =====================================================================
def _init():
    ss = st.session_state
    ss.setdefault("cmp_carrito", [])
    ss.setdefault("cmp_pagos", [])
    ss.setdefault("cmp_gastos", {"flete": 0.0, "otros": 0.0, "iva": 0.0})
    ss.setdefault("cmp_key", str(uuid.uuid4()))
    ss.setdefault("cmp_ok", None)
    ss.setdefault("cmp_msgs", [])


def _toast(texto, icono="✅"):
    st.session_state.cmp_msgs.append((texto, icono))


def _prorratear() -> bool:
    return U.es_verdadero(st.session_state._cmp_cfg.get("prorratear_gastos", "true"))


def _totales(pagos=None) -> dict:
    ss = st.session_state
    g = ss.cmp_gastos
    return U.calcular_compra(ss.cmp_carrito, g["flete"], g["otros"], g["iva"],
                             ss.cmp_pagos if pagos is None else pagos, ss._cmp_tasa, _prorratear())


def _reiniciar():
    ss = st.session_state
    ss.cmp_carrito = []
    ss.cmp_pagos = []
    ss.cmp_gastos = {"flete": 0.0, "otros": 0.0, "iva": 0.0}
    ss.cmp_key = str(uuid.uuid4())
    for k in list(ss.keys()):
        if k.startswith(("cmpd_", "cmp_w_")) or k in ("cmp_factura", "cmp_busqueda", "cmp_prov"):
            del ss[k]


def _buscar(texto: str, categoria_id):
    palabras = [p for p in texto.replace(",", " ").replace("(", " ").replace(")", " ").split() if p]
    q = supabase.table("productos").select(COLS, count="exact").eq("activo", True)
    if categoria_id:
        q = q.eq("categoria_id", categoria_id)
    if palabras:
        q = q.or_(f"sku.ilike.%{palabras[0]}%,nombre.ilike.%{palabras[0]}%,marca.ilike.%{palabras[0]}%")
    res = q.order("stock_actual").order("nombre").limit(60).execute()
    datos = res.data or []
    resto = [p.lower() for p in palabras[1:]]
    if resto:
        datos = [d for d in datos if all(p in f"{d['sku']} {d['nombre']} {d.get('marca') or ''}".lower() for p in resto)]
    total = len(datos) if resto else (res.count or len(datos))
    return datos[:12], total


def _indicador_margen(precio, costo):
    m = U.margen_pct(precio, costo)
    if m is None:
        st.warning("Este producto no tiene precio de venta. Márcalo para asignarle uno.")
    elif m < 0:
        st.error(f"⚠️ Con este costo venderías **con pérdida** (margen {U.fmt_num(m, 1)}%).")
    elif m < 15:
        st.warning(f"Margen bajo: **{U.fmt_num(m, 1)}%** sobre el precio de venta.")
    else:
        st.success(f"Margen de ganancia: **{U.fmt_num(m, 1)}%** sobre el precio de venta.")


# =====================================================================
# VENTANA · PRODUCTO A COMPRAR (agregar o editar línea)
# =====================================================================
@st.dialog("📦 Producto a comprar")
def dialog_linea(prod: dict):
    ss = st.session_state
    tasa = ss._cmp_tasa
    idx = next((i for i, it in enumerate(ss.cmp_carrito) if it["producto_id"] == prod["id"]), None)
    linea = ss.cmp_carrito[idx] if idx is not None else {}
    costo_act = U.D(prod.get("costo_usd"))
    precio_act = U.D(prod.get("precio_usd"))

    st.markdown(f"### {prod['nombre']}")
    st.caption(f"SKU `{prod['sku']}`" + (f" · {prod['marca']}" if prod.get("marca") else ""))
    c1, c2, c3 = st.columns(3)
    c1.metric("Stock actual", int(prod.get("stock_actual") or 0))
    c2.metric("Costo actual", U.fmt_usd(costo_act))
    c3.metric("Precio de venta", U.fmt_usd(precio_act))

    a, b = st.columns(2)
    cantidad = a.number_input("Cantidad que compras", min_value=1, step=1, value=int(linea.get("cantidad", 1)))
    costo = b.number_input("Costo unitario (USD)", min_value=0.0, step=0.01, format="%.2f",
                           value=float(linea.get("costo_usd", costo_act)))
    sub = U.r2(U.D(cantidad) * U.D(costo))
    st.info(f"**Subtotal:** {U.fmt_usd(sub)}  ·  {U.fmt_bs(sub * tasa)}")
    if costo == 0:
        st.caption("Costo $0: se registrará como bonificación / obsequio del proveedor.")
    elif costo_act > 0 and U.D(costo) != costo_act:
        variacion = (U.D(costo) - costo_act) / costo_act * 100
        st.caption(("📈 Sube " if variacion > 0 else "📉 Baja ") + f"{U.fmt_num(abs(variacion), 1)}% "
                   f"respecto al costo actual ({U.fmt_usd(costo_act)}).")

    actualizar = st.checkbox("🏷️ Actualizar también el precio de venta",
                             value=linea.get("precio_venta_usd") is not None or precio_act <= 0)
    precio_nuevo = None
    if actualizar:
        sugerido = linea.get("precio_venta_usd") or (float(precio_act) if precio_act > 0 else round(costo * 1.5, 2))
        precio_nuevo = st.number_input("Nuevo precio de venta (USD)", min_value=0.01, step=0.01, format="%.2f",
                                       value=float(sugerido or 0.01))
    _indicador_margen(precio_nuevo if precio_nuevo else precio_act, costo)

    st.divider()
    x, y = st.columns(2)
    if x.button("Cancelar", use_container_width=True):
        st.rerun()
    if y.button("✅ Guardar en la compra" if idx is not None else "✅ Agregar a la compra",
                type="primary", use_container_width=True):
        nueva = {"producto_id": prod["id"], "sku": prod["sku"], "nombre": prod["nombre"],
                 "cantidad": int(cantidad), "costo_usd": float(costo),
                 "precio_venta_usd": float(precio_nuevo) if precio_nuevo else None,
                 "stock": int(prod.get("stock_actual") or 0), "costo_actual": float(costo_act),
                 "precio_actual": float(precio_act), "marca": prod.get("marca")}
        if idx is not None:
            ss.cmp_carrito[idx] = nueva
        else:
            ss.cmp_carrito.append(nueva)
        _toast(f"{prod['nombre']}: {cantidad} und a {U.fmt_usd(costo)}")
        st.rerun()


def _linea_como_producto(it: dict) -> dict:
    return {"id": it["producto_id"], "sku": it["sku"], "nombre": it["nombre"], "marca": it.get("marca"),
            "stock_actual": it["stock"], "costo_usd": it["costo_actual"], "precio_usd": it["precio_actual"]}


# =====================================================================
# VENTANA · PRODUCTO NUEVO (que compras por primera vez)
# =====================================================================
@st.dialog("🆕 Producto nuevo", width="large")
def dialog_producto_nuevo():
    st.caption("Para productos que compras por primera vez. Se crea en el catálogo y entra directo a esta compra.")
    categorias = obtener_categorias()
    if not categorias:
        st.warning("Primero crea una categoría en el módulo Productos.")
        return
    cat = st.selectbox("Categoría", categorias, format_func=lambda c: c["nombre"])
    sku = generar_sku(cat["nombre"])
    st.caption(f"🔢 SKU que se asignará: **{sku}**")
    nombre = st.text_input("Nombre del producto *")
    c1, c2 = st.columns(2)
    marca = c1.text_input("Marca")
    minimo = c2.number_input("Stock mínimo", min_value=0, step=1, value=2)
    c3, c4, c5 = st.columns(3)
    cantidad = c3.number_input("Cantidad que compras", min_value=1, step=1, value=1)
    costo = c4.number_input("Costo unitario (USD) *", min_value=0.0, step=0.01, format="%.2f")
    precio = c5.number_input("Precio de venta (USD) *", min_value=0.0, step=0.01, format="%.2f")
    exento = st.checkbox("Exento de IVA")
    if precio > 0:
        _indicador_margen(precio, costo)

    st.divider()
    x, y = st.columns(2)
    if x.button("Cancelar", use_container_width=True):
        st.rerun()
    if y.button("✅ Crear y agregar a la compra", type="primary", use_container_width=True):
        if not nombre.strip() or precio <= 0:
            st.error("El nombre y el precio de venta son obligatorios.")
            return
        try:
            r = supabase.table("productos").insert({
                "sku": sku, "nombre": nombre.strip(), "marca": marca.strip() or None, "categoria_id": cat["id"],
                "precio_usd": precio, "costo_usd": costo, "stock_actual": 0, "stock_minimo": int(minimo),
                "exento_iva": exento, "activo": True,
            }).execute()
        except Exception as e:
            st.error(U.mensaje_error(e))
            return
        p = r.data[0]
        st.session_state.cmp_carrito.append({
            "producto_id": p["id"], "sku": p["sku"], "nombre": p["nombre"], "marca": p.get("marca"),
            "cantidad": int(cantidad), "costo_usd": float(costo), "precio_venta_usd": None,
            "stock": 0, "costo_actual": float(costo), "precio_actual": float(precio)})
        _toast(f"Producto {sku} creado y agregado")
        st.rerun()


# =====================================================================
# VENTANA · PAGAR Y REGISTRAR
# =====================================================================
def _cb_pago(exacto: bool):
    ss = st.session_state
    etiqueta = ss.get("cmpd_metodo") or list(METODOS)[0]
    nombre, moneda, requiere_ref = METODOS[etiqueta]
    referencia = (ss.get("cmpd_ref") or "").strip()
    t = _totales()
    if exacto:
        monto = t["falta_usd"] if moneda == "USD" else t["falta_bs"]
    else:
        monto = U.r2(ss.get("cmpd_monto") or 0)
    if monto <= 0:
        ss.cmpd_aviso = "Escribe un monto mayor que cero."
        return
    if requiere_ref and not referencia:
        ss.cmpd_aviso = f"{nombre} necesita el número de referencia."
        return
    ss.cmp_pagos.append({"metodo": nombre, "moneda": moneda, "monto": float(monto), "referencia": referencia})
    ss.cmpd_monto = 0.0
    ss.cmpd_ref = ""
    ss.cmpd_aviso = None


def _registrar():
    ss = st.session_state
    g = ss.cmp_gastos
    items = [{"producto_id": it["producto_id"], "cantidad": it["cantidad"], "costo_usd": it["costo_usd"],
              "precio_venta_usd": it["precio_venta_usd"]} for it in ss.cmp_carrito]
    try:
        with st.spinner("Registrando compra..."):
            r = supabase.rpc("registrar_compra", {
                "p_proveedor_id": ss._cmp_prov["id"], "p_items": items, "p_pagos": ss.cmp_pagos,
                "p_flete_usd": g["flete"], "p_otros_usd": g["otros"], "p_iva_usd": g["iva"],
                "p_factura_proveedor": ss.get("_cmp_factura") or None,
                "p_observaciones": ss.get("cmpd_obs") or None, "p_idempotency_key": ss.cmp_key,
            }).execute()
        datos = r.data
    except Exception as e:
        st.error(f"No se pudo registrar la compra: {U.mensaje_error(e)}")
        return
    ss.cmp_ok = datos["compra_id"]
    _reiniciar()
    st.rerun()


@st.dialog("💰 Pagar y registrar compra", width="large")
def dialog_pagar():
    ss = st.session_state
    tasa, prov = ss._cmp_tasa, ss._cmp_prov
    t = _totales()

    st.caption(f"Proveedor: **{prov['nombre']}** · {prov['rif']}"
               + (f"  ·  Factura N° {ss['_cmp_factura']}" if ss.get("_cmp_factura") else ""))
    m1, m2 = st.columns(2)
    m1.metric("A pagar en bolívares", U.fmt_bs(t["total_bs"]))
    m2.metric("Total cotizado", U.fmt_usd(t["total_usd"]))
    st.caption(f"{U.fmt_usd(t['total_usd'])} × Bs. {U.fmt_num(tasa, 4)} (tasa BCV del día) · Pago de contado")

    pagado = float(min(max(t["pagado_bs"] / t["total_bs"], 0), 1)) if t["total_bs"] > 0 else 1.0
    st.progress(pagado, text="Pagado 100 %" if t["completo"] else
                f"Pagado {pagado * 100:.0f} %  ·  Falta {U.fmt_bs(t['falta_bs'])}")

    for i, p in enumerate(ss.cmp_pagos):
        with st.container(border=True):
            a, b, c = st.columns([5, 3, 1])
            a.markdown(f"**{p['metodo']}**" + (f"  ·  Ref {p['referencia']}" if p["referencia"] else ""))
            b.markdown(U.fmt_usd(p["monto"]) if p["moneda"] == "USD" else U.fmt_bs(p["monto"]))
            if c.button("✖", key=f"cmpd_quitar_{i}"):
                ss.cmp_pagos.pop(i)
                st.rerun(scope="fragment")

    if not t["completo"]:
        st.markdown("#### ¿Cómo le pagas al proveedor?")
        etiqueta = st.pills("Método", list(METODOS), default=list(METODOS)[0], key="cmpd_metodo",
                            label_visibility="collapsed") or list(METODOS)[0]
        nombre, moneda, requiere_ref = METODOS[etiqueta]
        if requiere_ref:
            st.text_input("Número de referencia *", key="cmpd_ref")
        exacto = U.fmt_usd(t["falta_usd"]) if moneda == "USD" else U.fmt_bs(t["falta_bs"])
        st.button(f"⚡ Pagar el monto exacto: {exacto}", type="primary", use_container_width=True,
                  on_click=_cb_pago, args=(True,))
        with st.expander("💡 Pago dividido (ej. parte en efectivo y parte por transferencia)"):
            st.number_input(f"Monto pagado en {'dólares' if moneda == 'USD' else 'bolívares'}",
                            min_value=0.0, step=1.0, format="%.2f", key="cmpd_monto")
            st.button("➕ Registrar este monto", use_container_width=True, on_click=_cb_pago, args=(False,))
        if ss.get("cmpd_aviso"):
            st.warning(ss.cmpd_aviso)
    else:
        st.success("✅ **Pago completo.** Revisa y confirma.")
        if t["ajuste_bs"] > 0:
            if t["ajuste_bs"] > t["total_bs"] * U.D("0.01"):
                st.warning(f"Pagaste {U.fmt_bs(t['ajuste_bs'])} de más. Es mucho para un redondeo: revisa los montos.")
            else:
                st.caption(f"Se registrará un ajuste por redondeo de {U.fmt_bs(t['ajuste_bs'])}.")

    st.text_input("Observaciones (opcional)", key="cmpd_obs")
    st.divider()
    a, b = st.columns(2)
    if a.button("← Volver a la compra", use_container_width=True):
        st.rerun()
    if b.button("✅ Confirmar compra", type="primary", use_container_width=True, disabled=not t["completo"]):
        _registrar()


# =====================================================================
# VENTANAS · RESULTADO Y DETALLE
# =====================================================================
def _tabla_cambios(detalle: list):
    filas = []
    for d in detalle:
        fila = {"Producto": f"{d['sku']} · {d['descripcion']}", "Cant.": d["cantidad"],
                "Stock": f"{U.fmt_num(d['stock_anterior'], 0)} → {U.fmt_num(U.D(d['stock_anterior']) + d['cantidad'], 0)}",
                "Costo $": f"{U.fmt_num(d['costo_anterior_usd'])} → {U.fmt_num(d['costo_nuevo_usd'])}"}
        if d.get("precio_venta_nuevo") is not None:
            fila["Precio venta $"] = f"{U.fmt_num(d['precio_venta_anterior'])} → {U.fmt_num(d['precio_venta_nuevo'])}"
        filas.append(fila)
    st.dataframe(pd.DataFrame(filas), hide_index=True, use_container_width=True)


@st.dialog("✅ ¡Compra registrada!", width="large")
def dialog_exito(compra_id: int):
    cfg = st.session_state._cmp_cfg
    compra, detalle, pagos = cargar_compra(supabase, compra_id)
    st.markdown(f"### Compra **{compra['numero']}** · {compra['proveedor_nombre']}")
    m1, m2 = st.columns(2)
    m1.metric("Pagado", U.fmt_bs(compra["pagado_bs"]))
    m2.metric("Total USD", U.fmt_usd(compra["total_usd"]))
    st.markdown("**Así quedó tu inventario:**")
    _tabla_cambios(detalle)
    html = generar_html_compra(compra, detalle, pagos, cfg)
    with st.expander("🧾 Ver comprobante de compra"):
        components.html(html, height=520, scrolling=True)
    a, b = st.columns(2)
    a.download_button("⬇️ Descargar comprobante", html.encode("utf-8"), file_name=f"{compra['numero']}.html",
                      mime="text/html", use_container_width=True, on_click="ignore")
    if b.button("📥 Nueva compra", type="primary", use_container_width=True):
        st.rerun()


@st.dialog("🧾 Detalle de compra", width="large")
def dialog_detalle(compra_id: int):
    cfg = st.session_state._cmp_cfg
    compra, detalle, pagos = cargar_compra(supabase, compra_id)
    _tabla_cambios(detalle)
    html = generar_html_compra(compra, detalle, pagos, cfg)
    components.html(html, height=480, scrolling=True)
    st.download_button("⬇️ Descargar comprobante", html.encode("utf-8"), file_name=f"{compra['numero']}.html",
                       mime="text/html", use_container_width=True, on_click="ignore")
    if compra["estado"] == "ANULADA":
        st.error(f"Anulada el {U.fecha_hora_local(compra['anulada_at'])}: {compra['motivo_anulacion']}")
        return
    usuario = st.session_state.get("usuario")
    if not U.es_admin(cfg, getattr(usuario, "email", None)):
        st.caption("Solo un administrador puede anular compras.")
        return
    with st.expander("↩️ Anular esta compra"):
        st.caption("Descuenta del stock lo que entró y restaura el costo anterior. "
                   "Solo es posible si la mercancía no se ha vendido.")
        motivo = st.text_area("Motivo (mínimo 10 caracteres)", key="cmpd_motivo_anula")
        seguro = st.checkbox("Confirmo que deseo anular esta compra", key="cmpd_confirma_anula")
        if st.button("Anular compra", type="primary", disabled=not seguro):
            try:
                supabase.rpc("anular_compra", {"p_compra_id": compra_id, "p_motivo": motivo}).execute()
            except Exception as e:
                st.error(U.mensaje_error(e))
            else:
                _toast(f"Compra {compra['numero']} anulada")
                st.rerun()


# =====================================================================
# PANTALLA PRINCIPAL
# =====================================================================
def _seccion_proveedor():
    ss = st.session_state
    st.subheader("1️⃣ Proveedor")
    proveedores = obtener_proveedores()
    por_id = {p["id"]: p for p in proveedores}
    ids = list(por_id)
    nuevo = ss.pop("_prov_creado", None)
    if nuevo:                       # recién creado en la ventana → queda seleccionado
        ss.pop("cmp_prov", None)
        actual = nuevo
    else:
        actual = ss.get("cmp_prov")
    c1, c2, c3 = st.columns([4, 3, 2])
    prov_id = c1.selectbox("Proveedor", ids, index=ids.index(actual) if actual in ids else None, key="cmp_prov",
                           format_func=lambda i: f"{por_id[i]['nombre']} · {por_id[i]['rif']}",
                           placeholder="Elige a quién le compras…", label_visibility="collapsed")
    c2.text_input("Factura del proveedor", key="cmp_factura", placeholder="N° factura / nota del proveedor (opcional)",
                  label_visibility="collapsed")
    if c3.button("➕ Nuevo proveedor", use_container_width=True):
        dialog_proveedor()
    ss._cmp_prov = por_id.get(prov_id)
    ss._cmp_factura = (ss.get("cmp_factura") or "").strip()
    if not proveedores:
        st.info("Aún no tienes proveedores. Presiona **➕ Nuevo proveedor**.")


def _catalogo(tasa):
    st.subheader("2️⃣ Productos que compras")
    c1, c2 = st.columns([4, 2])
    c1.text_input("Buscar", key="cmp_busqueda", label_visibility="collapsed",
                  placeholder="🔍 Nombre, SKU o marca (los de menor stock aparecen primero)")
    if c2.button("🆕 Producto nuevo", use_container_width=True):
        dialog_producto_nuevo()
    cats = obtener_categorias()
    nombres = ["Todas"] + [c["nombre"] for c in cats]
    cat_sel = st.pills("Categoría", nombres, default="Todas", key="cmp_cat", label_visibility="collapsed")
    cat_id = next((c["id"] for c in cats if c["nombre"] == cat_sel), None)
    try:
        productos, total = _buscar((st.session_state.get("cmp_busqueda") or "").strip(), cat_id)
    except Exception as e:
        st.error(U.mensaje_error(e))
        return
    if not productos:
        st.info("No hay coincidencias. Si es un producto que nunca has tenido, usa **🆕 Producto nuevo**.")
        return
    if total > len(productos):
        st.caption(f"Mostrando {len(productos)} de {total}. Usa el buscador para encontrar más rápido.")

    en_compra = {it["producto_id"] for it in st.session_state.cmp_carrito}
    cols = st.columns(3)
    for i, p in enumerate(productos):
        stock = int(p.get("stock_actual") or 0)
        minimo_txt = "❌ Agotado" if stock <= 0 else (f"⚠️ Stock {stock}" if stock <= 3 else f"Stock {stock}")
        with cols[i % 3].container(border=True):
            st.markdown(f"**{p['nombre']}**")
            st.caption(f"`{p['sku']}`" + (f" · {p['marca']}" if p.get("marca") else ""))
            st.markdown(f"Costo **{U.fmt_usd(p.get('costo_usd'))}** · Venta {U.fmt_usd(p.get('precio_usd'))}")
            st.caption(minimo_txt)
            etiqueta = "✏️ En la compra" if p["id"] in en_compra else "➕ Agregar"
            if st.button(etiqueta, key=f"cmp_add_{p['id']}", use_container_width=True):
                dialog_linea(p)


def _compra_actual(tasa):
    ss = st.session_state
    st.subheader("📋 Compra actual")
    if not ss.cmp_carrito:
        st.info("Aún no hay productos.\n\nBusca a la izquierda y presiona **➕ Agregar**.")
        return

    for i, it in enumerate(ss.cmp_carrito):
        sub = U.r2(U.D(it["cantidad"]) * U.D(it["costo_usd"]))
        with st.container(border=True):
            a, b = st.columns([3, 2])
            a.markdown(f"**{it['nombre']}**")
            a.caption(f"{it['sku']} · {U.fmt_usd(it['costo_usd'])} c/u"
                      + (f" · 🏷️ venta → {U.fmt_usd(it['precio_venta_usd'])}" if it["precio_venta_usd"] else ""))
            b.markdown(f"<div style='text-align:right'><b>{U.fmt_usd(sub)}</b><br>"
                       f"<small>{U.fmt_bs(sub * tasa)}</small></div>", unsafe_allow_html=True)
            m1, m2, m3, m4, m5 = st.columns(5)
            if m1.button("➖", key=f"cmp_menos_{i}", use_container_width=True, disabled=it["cantidad"] <= 1):
                it["cantidad"] -= 1
                st.rerun()
            m2.markdown(f"<div style='text-align:center;padding-top:.45rem'><b>{it['cantidad']}</b></div>",
                        unsafe_allow_html=True)
            if m3.button("➕", key=f"cmp_mas_{i}", use_container_width=True):
                it["cantidad"] += 1
                st.rerun()
            if m4.button("✏️", key=f"cmp_edit_{i}", use_container_width=True, help="Cambiar costo o precio"):
                dialog_linea(_linea_como_producto(it))
            if m5.button("🗑️", key=f"cmp_borrar_{i}", use_container_width=True, help="Quitar"):
                ss.cmp_carrito.pop(i)
                st.rerun()

    g = ss.cmp_gastos
    with st.expander("🚚 Flete, otros gastos e IVA de la compra (opcional)"):
        c1, c2, c3 = st.columns(3)
        g["flete"] = c1.number_input("Flete $", min_value=0.0, step=1.0, format="%.2f", value=g["flete"], key="cmp_w_flete")
        g["otros"] = c2.number_input("Otros gastos $", min_value=0.0, step=1.0, format="%.2f", value=g["otros"], key="cmp_w_otros")
        g["iva"] = c3.number_input("IVA cobrado $", min_value=0.0, step=1.0, format="%.2f", value=g["iva"], key="cmp_w_iva")
        if _prorratear():
            st.caption("El flete y otros gastos se reparten en el costo de cada producto (costo real). "
                       "El IVA no forma parte del costo.")

    t = _totales(pagos=[])
    unidades = sum(it["cantidad"] for it in ss.cmp_carrito)
    extras = []
    for etiqueta, clave in (("Flete", "flete_usd"), ("Otros", "otros_usd"), ("IVA", "iva_usd")):
        if t[clave] > 0:
            extras.append(f"{etiqueta} {U.fmt_usd(t[clave])}")
    st.markdown(f"""
    <div class="pos-total">
      <div class="lbl">TOTAL A PAGAR AL PROVEEDOR · {unidades} unidad(es)</div>
      <div class="bs">{U.fmt_bs(t['total_bs'])}</div>
      <div class="usd">{U.fmt_usd(t['total_usd'])}</div>
      <div class="det">Productos {U.fmt_usd(t['subtotal_usd'])}{' · ' + ' · '.join(extras) if extras else ''}
           · Tasa BCV {U.fmt_num(tasa, 4)}</div>
    </div>""", unsafe_allow_html=True)

    st.subheader("3️⃣ Paga y registra")
    if not ss._cmp_prov:
        st.caption("⚠️ Elige el proveedor arriba para poder pagar.")
    if st.button("💰 PAGAR Y REGISTRAR", type="primary", use_container_width=True, disabled=not ss._cmp_prov):
        ss.cmpd_aviso = None
        dialog_pagar()
    if st.button("Cancelar compra", use_container_width=True):
        _reiniciar()
        st.rerun()


def _historial():
    hoy = U.hoy_vzla()
    proveedores = obtener_proveedores(solo_activos=False)
    c1, c2, c3, c4 = st.columns([2, 2, 3, 2])
    desde = c1.date_input("Desde", hoy.replace(day=1), key="hc_desde", format="DD/MM/YYYY")
    hasta = c2.date_input("Hasta", hoy, key="hc_hasta", format="DD/MM/YYYY")
    prov = c3.selectbox("Proveedor", [None] + [p["id"] for p in proveedores], key="hc_prov",
                        format_func=lambda i: "Todos" if i is None else next(p["nombre"] for p in proveedores if p["id"] == i))
    estado = c4.selectbox("Estado", ["Todas", "REGISTRADA", "ANULADA"], key="hc_estado")
    if hasta < desde or (hasta - desde) > timedelta(days=366):
        st.warning("Revisa el rango de fechas (máximo un año).")
        return
    ini, fin = U.rango_dia_iso(desde, hasta)
    try:
        q = supabase.table("compras").select("*").gte("fecha", ini).lte("fecha", fin).order("fecha", desc=True)
        if prov:
            q = q.eq("proveedor_id", prov)
        if estado != "Todas":
            q = q.eq("estado", estado)
        compras = q.limit(1000).execute().data or []
    except Exception as e:
        st.error(U.mensaje_error(e))
        return
    if not compras:
        st.info("No hay compras en el período.")
        return

    validas = [c for c in compras if c["estado"] == "REGISTRADA"]
    m1, m2, m3 = st.columns(3)
    m1.metric("Compras", len(validas))
    m2.metric("Total USD", U.fmt_usd(sum(U.D(c["total_usd"]) for c in validas)))
    m3.metric("Total pagado Bs", U.fmt_bs(sum(U.D(c["pagado_bs"]) for c in validas)))

    for c in compras[:50]:
        with st.container(border=True):
            a, b, d, e = st.columns([3, 3, 2, 1])
            a.markdown(f"**{c['numero']}**" + ("  ❌ ANULADA" if c["estado"] == "ANULADA" else ""))
            a.caption(U.fecha_hora_local(c["fecha"]))
            b.markdown(c["proveedor_nombre"])
            b.caption(f"Factura {c['factura_proveedor']}" if c.get("factura_proveedor") else c["proveedor_rif"])
            d.markdown(f"**{U.fmt_usd(c['total_usd'])}**")
            d.caption(U.fmt_bs(c["pagado_bs"]))
            if e.button("👁️", key=f"hc_ver_{c['id']}", use_container_width=True, help="Ver detalle"):
                dialog_detalle(c["id"])

    tabla = pd.DataFrame([{
        "N°": c["numero"], "Fecha": U.fecha_hora_local(c["fecha"]), "Proveedor": c["proveedor_nombre"],
        "RIF": c["proveedor_rif"], "Factura proveedor": c.get("factura_proveedor") or "",
        "Total $": float(c["total_usd"]), "Tasa": float(c["tasa_bcv"]), "Pagado Bs": float(c["pagado_bs"]),
        "Estado": c["estado"]} for c in compras])
    st.download_button("⬇️ Descargar listado (CSV)", tabla.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"compras_{desde}_{hasta}.csv", mime="text/csv", on_click="ignore")
    if validas:
        with st.expander("📊 Compras por proveedor en el período"):
            df = pd.DataFrame([{"Proveedor": c["proveedor_nombre"], "Total $": float(c["total_usd"]),
                                "Pagado Bs": float(c["pagado_bs"])} for c in validas])
            res = df.groupby("Proveedor", as_index=False).agg(
                Compras=("Total $", "count"), **{"Total $": ("Total $", "sum"), "Pagado Bs": ("Pagado Bs", "sum")}
            ).sort_values("Total $", ascending=False)
            st.dataframe(res, hide_index=True, use_container_width=True, column_config={
                "Total $": st.column_config.NumberColumn(format="%.2f"),
                "Pagado Bs": st.column_config.NumberColumn(format="%.2f")})


def render():
    _init()
    ss = st.session_state
    st.markdown(CSS, unsafe_allow_html=True)
    cfg = U.obtener_config(supabase)
    fecha_tasa, tasa = U.tasa_vigente(supabase)
    ss._cmp_cfg, ss._cmp_tasa = cfg, tasa

    st.title("📥 Compras a proveedores")
    if not tasa:
        st.error("⚠️ No hay tasa BCV registrada. Regístrala en **💱 Tasa BCV** para poder comprar.")
        return
    metodo = "último costo" if cfg.get("metodo_costo", "ULTIMO").upper() == "ULTIMO" else "costo promedio"
    st.markdown(f"<span class='pos-tasa'>💱 Tasa BCV: <b>Bs. {U.fmt_num(tasa, 4)}</b> · fecha valor "
                f"{fecha_tasa:%d/%m/%Y}</span>", unsafe_allow_html=True)
    st.caption(f"Compras de contado: cotizas en USD y pagas en el acto en Bs. El costo se actualiza por **{metodo}**.")

    for texto, icono in ss.cmp_msgs:
        st.toast(texto, icon=icono)
    ss.cmp_msgs = []

    if ss.cmp_ok:
        compra_id = ss.cmp_ok
        ss.cmp_ok = None
        dialog_exito(compra_id)

    tab_nueva, tab_hist = st.tabs(["📥 Nueva compra", "📄 Historial de compras"])
    with tab_nueva:
        paso = 1 if not ss.get("cmp_prov") else (3 if ss.cmp_carrito else 2)
        _pasos(paso, ["1 · Elige el proveedor", "2 · Agrega productos", "3 · Paga y registra"])
        with st.expander("❓ ¿Cómo registrar una compra?"):
            st.markdown(
                "1. **Elige el proveedor** (o créalo con ➕ Nuevo proveedor) y, si quieres, el N° de su factura.\n"
                "2. **Busca cada producto** y presiona ➕ Agregar: indica cantidad y **costo en dólares**. "
                "Puedes aprovechar para actualizar el precio de venta; el sistema te muestra el margen.\n"
                "3. Si hubo **flete u otros gastos**, agrégalos: se reparten en el costo de cada producto.\n"
                "4. Presiona **💰 PAGAR Y REGISTRAR**, indica cómo pagaste y confirma. "
                "El stock sube, el costo se actualiza y todo queda en el Kardex.")
        _seccion_proveedor()
        st.divider()
        izq, der = st.columns([3, 2], gap="large")
        with izq:
            _catalogo(tasa)
        with der:
            _compra_actual(tasa)
    with tab_hist:
        _historial()
