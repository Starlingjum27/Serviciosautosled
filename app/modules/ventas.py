"""
PUNTO DE VENTA · versión guiada
=================================
Flujo en 3 pasos, cada uno con su ventana:
  1) Agregar productos   → ventana "Agregar al carrito"
  2) Cobrar              → ventana "Cobrar venta" (cliente + forma de pago)
  3) Comprobante         → ventana "¡Venta registrada!" (imprimir / descargar)

La venta se guarda en la base de datos con la función registrar_venta (todo o nada),
igual que antes: stock, kardex, IVA en Bs e IGTF sobre divisas.
"""
import uuid
from datetime import timedelta

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from app.db import supabase
from app import utils as U
from app.comprobante import cargar_venta, generar_html

# etiqueta visible -> (nombre guardado, moneda, requiere referencia)
METODOS = {
    "📱 Pago Móvil": ("Pago Móvil", "VES", True),
    "💳 Punto de venta": ("Punto de Venta", "VES", True),
    "💵 Efectivo Bs": ("Efectivo Bs", "VES", False),
    "🏦 Transferencia Bs": ("Transferencia Bs", "VES", True),
    "💲 Efectivo USD": ("Efectivo USD", "USD", False),
    "🇺🇸 Zelle": ("Zelle", "USD", True),
}
COLS = "id, sku, nombre, marca, precio_usd, stock_actual, exento_iva, activo, categoria_id"

CSS = """
<style>
.pos-pasos {display:flex; gap:.5rem; flex-wrap:wrap; margin:.25rem 0 1rem 0;}
.pos-paso {padding:.45rem 1rem; border-radius:999px; border:1px solid rgba(128,128,128,.35);
           font-size:.9rem; opacity:.55;}
.pos-paso.activo {border-color:#ff4b4b; background:rgba(255,75,75,.12); opacity:1; font-weight:600;}
.pos-paso.hecho {border-color:#21c354; background:rgba(33,195,84,.12); opacity:1;}
.pos-tasa {display:inline-block; padding:.35rem .9rem; border-radius:10px;
           background:rgba(28,131,225,.12); border:1px solid rgba(28,131,225,.4); font-size:.95rem;}
.pos-total {border-radius:14px; padding:1rem 1.2rem; background:rgba(128,128,128,.08);
            border:1px solid rgba(128,128,128,.25); margin:.5rem 0;}
.pos-total .lbl {font-size:.85rem; opacity:.7;}
.pos-total .bs {font-size:2rem; font-weight:700; line-height:1.2;}
.pos-total .usd {font-size:1.1rem; opacity:.85;}
.pos-total .det {font-size:.8rem; opacity:.65; margin-top:.4rem;}
.pos-precio {font-size:1.25rem; font-weight:700;}
.pos-vuelto {font-size:1.6rem; font-weight:700; color:#21c354;}
</style>
"""


# =====================================================================
# ESTADO Y AYUDAS
# =====================================================================
def _init():
    ss = st.session_state
    ss.setdefault("pos_carrito", [])
    ss.setdefault("pos_pagos", [])
    ss.setdefault("pos_cliente", {"modo": "final"})
    ss.setdefault("pos_key", str(uuid.uuid4()))
    ss.setdefault("pos_cobro_paso", 1)
    ss.setdefault("pos_venta_ok", None)
    ss.setdefault("pos_msgs", [])


def _toast(texto: str, icono: str = "✅"):
    st.session_state.pos_msgs.append((texto, icono))


def _permitir_sin_stock() -> bool:
    return U.es_verdadero(st.session_state._pos_cfg.get("permitir_venta_sin_stock"))


def _reiniciar_venta():
    ss = st.session_state
    ss.pos_carrito = []
    ss.pos_pagos = []
    ss.pos_cliente = {"modo": "final"}
    ss.pos_key = str(uuid.uuid4())
    ss.pos_cobro_paso = 1
    for k in list(ss.keys()):
        if k.startswith("dlg_") or k == "pos_busqueda":
            del ss[k]


def _pasos(actual: int, etiquetas: list[str]):
    html = ""
    for i, txt in enumerate(etiquetas, start=1):
        clase = "hecho" if i < actual else ("activo" if i == actual else "")
        marca = "✔ " if i < actual else ""
        html += f"<span class='pos-paso {clase}'>{marca}{txt}</span>"
    st.markdown(f"<div class='pos-pasos'>{html}</div>", unsafe_allow_html=True)


def _subtotal(it):
    return U.r2(U.D(it["precio_usd"]) * U.D(it["cantidad"]) * (1 - U.D(it["descuento_pct"]) / 100))


# =====================================================================
# CARRITO
# =====================================================================
def _agregar(prod: dict, cantidad: int, descuento: float = 0.0) -> bool:
    ss = st.session_state
    stock = int(prod.get("stock_actual") or 0)
    for it in ss.pos_carrito:
        if it["producto_id"] == prod["id"]:
            nueva = it["cantidad"] + cantidad
            if nueva > stock and not _permitir_sin_stock():
                _toast(f"Solo hay {stock} unidades de {prod['sku']}", "⚠️")
                return False
            it["cantidad"] = nueva
            it["descuento_pct"] = descuento or it["descuento_pct"]
            _toast(f"{prod['nombre']} → {nueva} und")
            return True
    if cantidad > stock and not _permitir_sin_stock():
        _toast(f"{prod['sku']} sin stock suficiente", "⚠️")
        return False
    ss.pos_carrito.append({
        "producto_id": prod["id"], "sku": prod["sku"], "nombre": prod["nombre"],
        "precio_usd": float(prod["precio_usd"] or 0), "stock": stock,
        "exento_iva": bool(prod.get("exento_iva")), "cantidad": int(cantidad),
        "descuento_pct": float(descuento),
    })
    _toast(f"Agregado: {prod['nombre']}")
    return True


def _cb_escaner():
    """Enter en el buscador con un SKU exacto = se agrega 1 unidad (lector de código de barras)."""
    texto = (st.session_state.get("pos_busqueda") or "").strip()
    if not texto:
        return
    try:
        res = (supabase.table("productos").select(COLS)
               .in_("sku", list({texto, texto.upper()})).eq("activo", True).limit(1).execute())
    except Exception as e:
        _toast(U.mensaje_error(e), "❌")
        return
    if res.data:
        _agregar(res.data[0], 1)
        st.session_state.pos_busqueda = ""


def _categorias() -> list[dict]:
    try:
        return supabase.table("categorias").select("id, nombre").order("nombre").execute().data or []
    except Exception:
        return []


def _buscar(texto: str, categoria_id):
    palabras = [p for p in texto.replace(",", " ").replace("(", " ").replace(")", " ").split() if p]
    q = supabase.table("productos").select(COLS, count="exact").eq("activo", True)
    if categoria_id:
        q = q.eq("categoria_id", categoria_id)
    if palabras:
        p0 = palabras[0]
        q = q.or_(f"sku.ilike.%{p0}%,nombre.ilike.%{p0}%,marca.ilike.%{p0}%")
    res = q.order("nombre").limit(60).execute()
    datos = res.data or []
    resto = [p.lower() for p in palabras[1:]]
    if resto:
        datos = [d for d in datos
                 if all(p in f"{d['sku']} {d['nombre']} {d.get('marca') or ''}".lower() for p in resto)]
    total = len(datos) if resto else (res.count or len(datos))
    return datos[:12], total


# =====================================================================
# VENTANA 1 · AGREGAR PRODUCTO
# =====================================================================
@st.dialog("➕ Agregar al carrito")
def dialog_agregar(prod: dict):
    ss = st.session_state
    tasa, cfg = ss._pos_tasa, ss._pos_cfg
    stock = int(prod.get("stock_actual") or 0)
    en_carrito = next((it["cantidad"] for it in ss.pos_carrito if it["producto_id"] == prod["id"]), 0)
    disponible = stock - en_carrito
    precio = U.D(prod["precio_usd"])

    st.markdown(f"### {prod['nombre']}")
    st.caption(f"SKU `{prod['sku']}`" + (f" · Marca {prod['marca']}" if prod.get("marca") else "")
               + (" · Exento de IVA" if prod.get("exento_iva") else ""))

    c1, c2, c3 = st.columns(3)
    c1.metric("Precio", U.fmt_usd(precio))
    c2.metric("En bolívares", U.fmt_bs(precio * tasa))
    c3.metric("Disponible", disponible, help=f"Stock {stock} − {en_carrito} ya en el carrito" if en_carrito else None)

    if disponible <= 0 and not _permitir_sin_stock():
        st.error("No quedan unidades disponibles de este producto.")
        if st.button("Cerrar", use_container_width=True):
            st.rerun()
        return

    cantidad = st.number_input("¿Cuántas unidades?", min_value=1, step=1, value=1,
                               max_value=None if _permitir_sin_stock() else disponible)
    descuento = 0.0
    desc_max = float(cfg.get("descuento_max_pct", 0) or 0)
    if desc_max > 0:
        with st.expander("🏷️ Aplicar descuento (opcional)"):
            descuento = st.slider("Descuento %", 0.0, desc_max, 0.0, 1.0)

    sub = U.r2(precio * cantidad * (1 - U.D(descuento) / 100))
    st.info(f"**Subtotal:** {U.fmt_usd(sub)}  ·  {U.fmt_bs(sub * tasa)}  (sin IVA)")

    a, b = st.columns(2)
    if a.button("Cancelar", use_container_width=True):
        st.rerun()
    if b.button("✅ Agregar al carrito", type="primary", use_container_width=True):
        _agregar(prod, int(cantidad), descuento)
        st.rerun()


# =====================================================================
# VENTANA 2 · COBRAR (A: cliente  →  B: pago)
# =====================================================================
def _cb_pago(exacto: bool):
    ss = st.session_state
    etiqueta = ss.get("dlg_metodo") or list(METODOS)[0]
    nombre, moneda, requiere_ref = METODOS[etiqueta]
    referencia = (ss.get("dlg_ref") or "").strip()
    if exacto:
        monto = U.monto_para_completar(ss.pos_carrito, ss.pos_pagos, ss._pos_tasa, ss._pos_cfg, moneda)
    else:
        monto = U.r2(ss.get("dlg_monto") or 0)
    if monto <= 0:
        ss.dlg_aviso = "Escribe un monto mayor que cero."
        return
    if requiere_ref and not referencia:
        ss.dlg_aviso = f"{nombre} necesita el número de referencia."
        return
    ss.pos_pagos.append({"metodo": nombre, "moneda": moneda, "monto": float(monto), "referencia": referencia})
    ss.dlg_monto = 0.0
    ss.dlg_ref = ""
    ss.dlg_aviso = None


def _paso_cliente():
    ss = st.session_state
    cli = ss.pos_cliente
    st.markdown("#### ¿A nombre de quién va la venta?")
    opciones = ["🙋 Consumidor final", "🪪 Cliente con Cédula / RIF"]
    modo = st.radio("Tipo de cliente", opciones, index=0 if cli.get("modo") == "final" else 1,
                    horizontal=True, label_visibility="collapsed", key="dlg_modo_cli")

    datos, error = {"modo": "final"}, None
    if modo == opciones[0]:
        st.info("La venta se emitirá a **CONSUMIDOR FINAL**. Ideal para ventas rápidas de mostrador.")
    else:
        tipos = ["V", "E", "J", "G", "P"]
        c1, c2 = st.columns([1, 3])
        tipo = c1.selectbox("Tipo", tipos, index=tipos.index(cli.get("tipo", "V")), key="dlg_tipo")
        numero = c2.text_input("Número", value=cli.get("numero", ""), placeholder="Ej: 12345678 ó 123456789",
                               key="dlg_numero")
        rif = U.normalizar_rif(tipo, numero) if numero else None
        if not numero:
            error = "Escribe la cédula o RIF."
        elif not rif:
            error = "La cédula/RIF debe tener entre 5 y 9 dígitos."
        else:
            existente = None
            try:
                r = supabase.table("clientes").select("*").eq("rif", rif).limit(1).execute()
                existente = r.data[0] if r.data else None
            except Exception:
                pass
            if existente:
                st.success(f"✅ Cliente registrado: **{existente['nombre']}** ({rif})")
            else:
                st.warning(f"🆕 {rif} no está registrado. Completa sus datos y se guardará automáticamente.")
            previo = cli if cli.get("rif") == rif else {}
            nombre = st.text_input("Nombre o razón social *",
                                   value=previo.get("nombre") or (existente or {}).get("nombre", ""),
                                   key=f"dlg_nombre_{rif}")
            c3, c4 = st.columns(2)
            telefono = c3.text_input("Teléfono",
                                     value=previo.get("telefono") or (existente or {}).get("telefono") or "",
                                     key=f"dlg_tel_{rif}")
            direccion = c4.text_input("Dirección",
                                      value=previo.get("direccion") or (existente or {}).get("direccion") or "",
                                      key=f"dlg_dir_{rif}")
            if not nombre.strip():
                error = "Escribe el nombre del cliente."
            datos = {"modo": "rif", "tipo": tipo, "numero": numero, "rif": rif, "nombre": nombre.strip(),
                     "telefono": telefono.strip(), "direccion": direccion.strip()}
        if error:
            st.caption(f"⚠️ {error}")

    st.divider()
    a, b = st.columns(2)
    if a.button("✖ Cancelar", use_container_width=True):
        st.rerun()
    if b.button("Siguiente: forma de pago →", type="primary", use_container_width=True, disabled=bool(error)):
        ss.pos_cliente = datos
        ss.pos_cobro_paso = 2
        st.rerun(scope="fragment")


def _paso_pago():
    ss = st.session_state
    tasa, cfg = ss._pos_tasa, ss._pos_cfg
    cli = ss.pos_cliente
    t = U.calcular_totales(ss.pos_carrito, ss.pos_pagos, tasa, cfg)

    c1, c2 = st.columns([4, 1])
    c1.caption("Cliente: " + ("**CONSUMIDOR FINAL**" if cli.get("modo") == "final"
                              else f"**{cli['nombre']}** · {cli['rif']}"))
    if c2.button("✏️ Cambiar", use_container_width=True):
        ss.pos_cobro_paso = 1
        st.rerun(scope="fragment")

    m1, m2 = st.columns(2)
    m1.metric("Total en bolívares", U.fmt_bs(t["total_bs"]))
    m2.metric("Total en divisas", U.fmt_usd(t["total_todo_divisas_usd"]),
              help=f"Incluye IGTF {U.fmt_num(t['igtf_pct'], 0)}%" if t["igtf_pct"] > 0 else None)

    pagado = float(1 - (t["falta_bs"] / t["total_bs"])) if t["total_bs"] > 0 else 0.0
    pagado = min(max(pagado, 0.0), 1.0)
    if t["completo"]:
        st.progress(1.0, text="Pagado 100 %")
    else:
        falta_usd = U.monto_para_completar(ss.pos_carrito, ss.pos_pagos, tasa, cfg, "USD")
        st.progress(pagado, text=f"Pagado {pagado * 100:.0f} %  ·  Falta {U.fmt_bs(t['falta_bs'])} "
                                 f"ó {U.fmt_usd(falta_usd)} en divisas")

    # Pagos ya registrados
    for i, p in enumerate(ss.pos_pagos):
        with st.container(border=True):
            a, b, c = st.columns([5, 3, 1])
            a.markdown(f"**{p['metodo']}**" + (f"  ·  Ref {p['referencia']}" if p["referencia"] else ""))
            b.markdown(U.fmt_usd(p["monto"]) if p["moneda"] == "USD" else U.fmt_bs(p["monto"]))
            if c.button("✖", key=f"dlg_quitar_{i}", help="Quitar este pago"):
                ss.pos_pagos.pop(i)
                st.rerun(scope="fragment")

    if not t["completo"]:
        st.markdown("#### ¿Cómo paga el cliente?")
        etiqueta = st.pills("Método de pago", list(METODOS), default=list(METODOS)[0],
                            key="dlg_metodo", label_visibility="collapsed") or list(METODOS)[0]
        nombre, moneda, requiere_ref = METODOS[etiqueta]
        exacto = U.monto_para_completar(ss.pos_carrito, ss.pos_pagos, tasa, cfg, moneda)
        texto_exacto = U.fmt_usd(exacto) if moneda == "USD" else U.fmt_bs(exacto)

        if requiere_ref:
            st.text_input("Número de referencia *", key="dlg_ref", placeholder="Últimos dígitos o N° de aprobación")
        st.button(f"⚡ Cobrar el monto exacto: {texto_exacto}", type="primary", use_container_width=True,
                  on_click=_cb_pago, args=(True,))
        with st.expander("💡 Pago parcial o mixto (ej. una parte en $ y el resto en Bs)"):
            st.number_input(f"Monto recibido en {'dólares' if moneda == 'USD' else 'bolívares'}",
                            min_value=0.0, step=1.0, format="%.2f", key="dlg_monto")
            st.button("➕ Registrar este monto", use_container_width=True, on_click=_cb_pago, args=(False,))
            st.caption("Registra cada parte por separado. El sistema calcula cuánto falta y el vuelto.")
        if ss.get("dlg_aviso"):
            st.warning(ss.dlg_aviso)
    else:
        vuelto = []
        if t["vuelto_usd"] > 0:
            vuelto.append(U.fmt_usd(t["vuelto_usd"]))
        if t["vuelto_bs"] > 0:
            vuelto.append(U.fmt_bs(t["vuelto_bs"]))
        st.success("✅ **Pago completo.** Revisa y confirma la venta.")
        if vuelto:
            st.markdown(f"Vuelto a entregar: <span class='pos-vuelto'>{' + '.join(vuelto)}</span>",
                        unsafe_allow_html=True)
        if t["igtf_usd"] > 0:
            st.caption(f"Incluye IGTF de {U.fmt_usd(t['igtf_usd'])} por el pago en divisas.")

    st.divider()
    a, b = st.columns(2)
    if a.button("← Volver", use_container_width=True):
        ss.pos_cobro_paso = 1
        st.rerun(scope="fragment")
    if b.button("✅ Confirmar venta", type="primary", use_container_width=True, disabled=not t["completo"]):
        _finalizar()


def _finalizar():
    ss = st.session_state
    cli = ss.pos_cliente
    cliente = {"rif": "", "nombre": "CONSUMIDOR FINAL"} if cli.get("modo") == "final" else {
        "rif": cli["rif"], "nombre": cli["nombre"], "telefono": cli.get("telefono", ""),
        "direccion": cli.get("direccion", "")}
    items = [{"producto_id": it["producto_id"], "cantidad": int(it["cantidad"]),
              "descuento_pct": float(it["descuento_pct"])} for it in ss.pos_carrito]
    try:
        with st.spinner("Registrando venta..."):
            res = supabase.rpc("registrar_venta", {
                "p_items": items, "p_pagos": ss.pos_pagos, "p_cliente": cliente,
                "p_observaciones": None, "p_idempotency_key": ss.pos_key,
            }).execute()
        datos = res.data
    except Exception as e:
        st.error(f"No se pudo registrar la venta: {U.mensaje_error(e)}")
        return
    ss.pos_venta_ok = datos["venta_id"]
    _reiniciar_venta()
    st.rerun()


@st.dialog("💳 Cobrar venta", width="large")
def dialog_cobrar():
    paso = st.session_state.pos_cobro_paso
    _pasos(paso, ["A · Cliente", "B · Forma de pago"])
    if paso == 1:
        _paso_cliente()
    else:
        _paso_pago()


# =====================================================================
# VENTANA 3 · VENTA REGISTRADA
# =====================================================================
@st.dialog("✅ ¡Venta registrada!", width="large")
def dialog_exito(venta_id: int):
    cfg = st.session_state._pos_cfg
    try:
        venta, detalle, pagos = cargar_venta(supabase, venta_id)
    except Exception as e:
        st.error(U.mensaje_error(e))
        return
    st.markdown(f"### Documento **{venta['numero']}**")
    m1, m2 = st.columns(2)
    m1.metric("Cobrado en Bs", U.fmt_bs(venta["total_pagar_bs"]))
    m2.metric("Equivalente USD", U.fmt_usd(venta["total_pagar_usd"]))
    vuelto = []
    if U.D(venta["vuelto_usd"]) > 0:
        vuelto.append(U.fmt_usd(venta["vuelto_usd"]))
    if U.D(venta["vuelto_bs"]) > 0:
        vuelto.append(U.fmt_bs(venta["vuelto_bs"]))
    if vuelto:
        st.markdown(f"Entrega de vuelto: <span class='pos-vuelto'>{' + '.join(vuelto)}</span>",
                    unsafe_allow_html=True)

    html = generar_html(venta, detalle, pagos, cfg)
    components.html(html, height=480, scrolling=True)
    st.caption("Usa el botón 🖨️ dentro del comprobante para imprimirlo.")
    a, b = st.columns(2)
    a.download_button("⬇️ Descargar comprobante", html.encode("utf-8"), file_name=f"{venta['numero']}.html",
                      mime="text/html", use_container_width=True, on_click="ignore")
    if b.button("🛒 Nueva venta", type="primary", use_container_width=True):
        st.rerun()


# =====================================================================
# VENTANA · DETALLE DE UNA VENTA (historial)
# =====================================================================
@st.dialog("🧾 Detalle de venta", width="large")
def dialog_detalle(venta_id: int):
    cfg = st.session_state._pos_cfg
    venta, detalle, pagos = cargar_venta(supabase, venta_id)
    html = generar_html(venta, detalle, pagos, cfg)
    components.html(html, height=480, scrolling=True)
    st.download_button("⬇️ Descargar comprobante", html.encode("utf-8"), file_name=f"{venta['numero']}.html",
                       mime="text/html", use_container_width=True, on_click="ignore")

    if venta["estado"] == "ANULADA":
        st.error(f"Anulada el {U.fecha_hora_local(venta['anulada_at'])}: {venta['motivo_anulacion']}")
        return
    usuario = st.session_state.get("usuario")
    if not U.es_admin(cfg, getattr(usuario, "email", None)):
        st.caption("Solo un administrador puede anular ventas.")
        return
    with st.expander("↩️ Anular esta venta"):
        st.caption("El stock regresa al inventario y se emite una nota de crédito con la tasa BCV original "
                   f"(Bs. {U.fmt_num(venta['tasa_bcv'], 4)}).")
        motivo = st.text_area("Motivo (mínimo 10 caracteres)", key="dlg_motivo_anula")
        seguro = st.checkbox("Confirmo que deseo anular esta venta", key="dlg_confirma_anula")
        if st.button("Anular venta", type="primary", disabled=not seguro):
            try:
                r = supabase.rpc("anular_venta", {"p_venta_id": venta_id, "p_motivo": motivo}).execute()
            except Exception as e:
                st.error(U.mensaje_error(e))
            else:
                _toast(f"Venta anulada · Nota de crédito {r.data['nota_credito']}")
                st.rerun()


# =====================================================================
# PANTALLA PRINCIPAL
# =====================================================================
def _catalogo(tasa):
    st.subheader("1️⃣ Busca y agrega productos")
    st.text_input("Buscar producto", key="pos_busqueda", on_change=_cb_escaner, label_visibility="collapsed",
                  placeholder="🔍 Escribe nombre, SKU o marca… o escanea el código de barras")

    cats = _categorias()
    nombres = ["Todas"] + [c["nombre"] for c in cats]
    cat_sel = st.pills("Categoría", nombres, default="Todas", key="pos_cat", label_visibility="collapsed")
    cat_id = next((c["id"] for c in cats if c["nombre"] == cat_sel), None)

    texto = (st.session_state.get("pos_busqueda") or "").strip()
    try:
        productos, total = _buscar(texto, cat_id)
    except Exception as e:
        st.error(f"Error buscando productos: {U.mensaje_error(e)}")
        return
    if not productos:
        st.info("No se encontraron productos. Prueba con otra palabra o categoría.")
        return
    if total > len(productos):
        st.caption(f"Mostrando {len(productos)} de {total}. Escribe en el buscador para encontrar más rápido.")

    cols = st.columns(3)
    for i, p in enumerate(productos):
        stock = int(p.get("stock_actual") or 0)
        with cols[i % 3].container(border=True):
            st.markdown(f"**{p['nombre']}**")
            st.caption(f"`{p['sku']}`" + (f" · {p['marca']}" if p.get("marca") else ""))
            st.markdown(f"<span class='pos-precio'>{U.fmt_usd(p['precio_usd'])}</span><br>"
                        f"<small>{U.fmt_bs(U.D(p['precio_usd']) * tasa)}</small>", unsafe_allow_html=True)
            if stock <= 0:
                st.caption("❌ Agotado")
            elif stock <= 3:
                st.caption(f"⚠️ Quedan {stock}")
            else:
                st.caption(f"✅ {stock} disponibles")
            if st.button("➕ Agregar", key=f"pos_add_{p['id']}", use_container_width=True,
                         disabled=stock <= 0 and not _permitir_sin_stock()):
                dialog_agregar(p)


def _ticket(tasa, cfg):
    ss = st.session_state
    st.subheader("🧾 Venta actual")

    if not ss.pos_carrito:
        st.info("Aún no hay productos.\n\nBusca un producto a la izquierda y presiona **➕ Agregar**.")
        return

    for i, it in enumerate(ss.pos_carrito):
        sub = _subtotal(it)
        with st.container(border=True):
            a, b = st.columns([3, 2])
            a.markdown(f"**{it['nombre']}**")
            a.caption(f"{it['sku']} · {U.fmt_usd(it['precio_usd'])} c/u"
                      + (f" · −{it['descuento_pct']:.0f}%" if it["descuento_pct"] else ""))
            b.markdown(f"<div style='text-align:right'><b>{U.fmt_usd(sub)}</b><br>"
                       f"<small>{U.fmt_bs(sub * tasa)}</small></div>", unsafe_allow_html=True)
            m1, m2, m3, m4 = st.columns(4)
            if m1.button("➖", key=f"pos_menos_{i}", use_container_width=True, disabled=it["cantidad"] <= 1):
                it["cantidad"] -= 1
                st.rerun()
            m2.markdown(f"<div style='text-align:center;padding-top:.45rem'><b>{it['cantidad']}</b></div>",
                        unsafe_allow_html=True)
            tope = it["cantidad"] >= it["stock"] and not _permitir_sin_stock()
            if m3.button("➕", key=f"pos_mas_{i}", use_container_width=True, disabled=tope):
                it["cantidad"] += 1
                st.rerun()
            if m4.button("🗑️", key=f"pos_borrar_{i}", use_container_width=True, help="Quitar del carrito"):
                ss.pos_carrito.pop(i)
                st.rerun()

    t = U.calcular_totales(ss.pos_carrito, [], tasa, cfg)
    unidades = sum(it["cantidad"] for it in ss.pos_carrito)
    igtf = ""
    if t["igtf_pct"] > 0:
        igtf = (f"<br>Si paga en divisas: {U.fmt_usd(t['total_todo_divisas_usd'])} "
                f"(incluye IGTF {U.fmt_num(t['igtf_pct'], 0)}%)")
    st.markdown(f"""
    <div class="pos-total">
      <div class="lbl">TOTAL A PAGAR · {unidades} unidad(es)</div>
      <div class="bs">{U.fmt_bs(t['total_bs'])}</div>
      <div class="usd">{U.fmt_usd(t['total_usd'])}</div>
      <div class="det">Base {U.fmt_bs(t['base_bs'] + t['exento_bs'])} · IVA {U.fmt_num(t['iva_pct'], 0)}%
           {U.fmt_bs(t['iva_bs'])}{igtf}</div>
    </div>""", unsafe_allow_html=True)

    st.subheader("2️⃣ Cobra")
    if st.button("💳 COBRAR", type="primary", use_container_width=True):
        ss.pos_cobro_paso = 1
        ss.dlg_aviso = None
        dialog_cobrar()
    if st.button("Cancelar venta", use_container_width=True):
        _reiniciar_venta()
        st.rerun()


def _historial(cfg):
    hoy = U.hoy_vzla()
    c1, c2, c3, c4 = st.columns([2, 2, 2, 3])
    desde = c1.date_input("Desde", hoy, key="hist_desde", format="DD/MM/YYYY")
    hasta = c2.date_input("Hasta", hoy, key="hist_hasta", format="DD/MM/YYYY")
    estado = c3.selectbox("Estado", ["Todas", "EMITIDA", "ANULADA"], key="hist_estado")
    texto = c4.text_input("Buscar N° o cliente", key="hist_texto")
    if hasta < desde or (hasta - desde) > timedelta(days=366):
        st.warning("Revisa el rango de fechas (máximo un año).")
        return

    ini, fin = U.rango_dia_iso(desde, hasta)
    try:
        q = supabase.table("ventas").select("*").gte("fecha", ini).lte("fecha", fin).order("fecha", desc=True)
        if estado != "Todas":
            q = q.eq("estado", estado)
        ventas = q.limit(1000).execute().data or []
    except Exception as e:
        st.error(U.mensaje_error(e))
        return
    if texto:
        t = texto.lower()
        ventas = [v for v in ventas if t in v["numero"].lower() or t in v["cliente_nombre"].lower()
                  or t in v["cliente_rif"].lower()]
    if not ventas:
        st.info("No hay ventas en el período seleccionado.")
        return

    emitidas = [v for v in ventas if v["estado"] == "EMITIDA"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Ventas", len(emitidas))
    m2.metric("Total USD", U.fmt_usd(sum(U.D(v["total_pagar_usd"]) for v in emitidas)))
    m3.metric("Total Bs", U.fmt_bs(sum(U.D(v["total_pagar_bs"]) for v in emitidas)))
    m4.metric("IGTF", U.fmt_usd(sum(U.D(v["igtf_usd"]) for v in emitidas)))

    for v in ventas[:50]:
        with st.container(border=True):
            a, b, c, d = st.columns([3, 3, 2, 1])
            a.markdown(f"**{v['numero']}**" + ("  ❌ ANULADA" if v["estado"] == "ANULADA" else ""))
            a.caption(U.fecha_hora_local(v["fecha"]))
            b.markdown(v["cliente_nombre"])
            b.caption(v["cliente_rif"])
            c.markdown(f"**{U.fmt_usd(v['total_pagar_usd'])}**")
            c.caption(U.fmt_bs(v["total_pagar_bs"]))
            if d.button("👁️", key=f"hist_ver_{v['id']}", help="Ver comprobante", use_container_width=True):
                dialog_detalle(v["id"])
    if len(ventas) > 50:
        st.caption(f"Se muestran 50 de {len(ventas)}. Descarga el CSV para verlas todas.")

    tabla = pd.DataFrame([{
        "N°": v["numero"], "Fecha": U.fecha_hora_local(v["fecha"]), "Cliente": v["cliente_nombre"],
        "RIF": v["cliente_rif"], "Total $": float(v["total_pagar_usd"]), "Total Bs": float(v["total_pagar_bs"]),
        "IGTF $": float(v["igtf_usd"]), "Tasa": float(v["tasa_bcv"]), "Estado": v["estado"],
    } for v in ventas])
    st.download_button("⬇️ Descargar listado (CSV)", tabla.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"ventas_{desde}_{hasta}.csv", mime="text/csv", on_click="ignore")

    with st.expander("💵 Cierre de caja (lo recibido por cada método de pago)"):
        ids = [v["id"] for v in emitidas]
        if not ids:
            st.info("Sin ventas emitidas.")
            return
        pagos = []
        for i in range(0, len(ids), 200):
            pagos += supabase.table("pagos_venta").select("metodo, moneda, monto").in_(
                "venta_id", ids[i:i + 200]).execute().data or []
        df = pd.DataFrame(pagos)
        resumen = df.groupby(["metodo", "moneda"], as_index=False)["monto"].sum()
        for _, r in resumen.iterrows():
            st.markdown(f"- **{r.metodo}**: {U.fmt_usd(r.monto) if r.moneda == 'USD' else U.fmt_bs(r.monto)}")
        st.caption(f"Vueltos entregados: {U.fmt_usd(sum(U.D(v['vuelto_usd']) for v in emitidas))} y "
                   f"{U.fmt_bs(sum(U.D(v['vuelto_bs']) for v in emitidas))}. Réstalos del efectivo al cuadrar.")


def render():
    _init()
    ss = st.session_state
    st.markdown(CSS, unsafe_allow_html=True)

    cfg = U.obtener_config(supabase)
    fecha_tasa, tasa = U.tasa_vigente(supabase)
    ss._pos_cfg, ss._pos_tasa = cfg, tasa

    st.title("🛒 Punto de Venta")
    if not tasa:
        st.error("⚠️ No hay tasa BCV registrada. Ve al módulo **💱 Tasa BCV** y regístrala para poder vender.")
        return

    dias = (U.hoy_vzla() - fecha_tasa).days
    st.markdown(f"<span class='pos-tasa'>💱 Tasa BCV: <b>Bs. {U.fmt_num(tasa, 4)}</b> · fecha valor "
                f"{fecha_tasa:%d/%m/%Y}</span>", unsafe_allow_html=True)
    if dias > int(cfg.get("tasa_dias_max", 4)):
        st.error(f"La tasa tiene {dias} días. Actualízala en **💱 Tasa BCV** antes de vender.")
    elif dias > 0 and U.hoy_vzla().weekday() < 5:
        st.warning("No hay tasa con fecha de hoy. Verifícala en bcv.org.ve y regístrala.")

    for texto, icono in ss.pos_msgs:
        st.toast(texto, icon=icono)
    ss.pos_msgs = []

    # Ventana de éxito tras confirmar una venta
    if ss.pos_venta_ok:
        venta_id = ss.pos_venta_ok
        ss.pos_venta_ok = None
        dialog_exito(venta_id)

    tab_vender, tab_hist = st.tabs(["🛒 Vender", "📄 Ventas del día y cierre"])
    with tab_vender:
        _pasos(2 if ss.pos_carrito else 1,
               ["1 · Agrega productos", "2 · Cobra al cliente", "3 · Entrega el comprobante"])
        with st.expander("❓ ¿Cómo hacer una venta?"):
            st.markdown(
                "1. **Busca** el producto por nombre, SKU o marca (o escanéalo) y presiona **➕ Agregar**.\n"
                "2. Ajusta cantidades en **Venta actual** con ➖ / ➕ y presiona **💳 COBRAR**.\n"
                "3. Elige el **cliente** y luego la **forma de pago**. Con **⚡ Cobrar el monto exacto** "
                "se registra todo en un clic; para pagos mixtos registra cada parte.\n"
                "4. Presiona **✅ Confirmar venta**: el stock se descuenta solo y aparece el comprobante."
            )
        izq, der = st.columns([3, 2], gap="large")
        with izq:
            _catalogo(tasa)
        with der:
            _ticket(tasa, cfg)
    with tab_hist:
        _historial(cfg)
