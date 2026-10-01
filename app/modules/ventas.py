"""
PUNTO DE VENTA — Fase 3
  🛒 Nueva venta : búsqueda / lector de código, carrito editable, cliente,
                   pagos mixtos Bs + divisas, IGTF, comprobante imprimible.
  📄 Historial   : consulta, reimpresión, resumen de caja por método y anulación
                   (nota de crédito con la tasa original).
Toda la venta se procesa en la BD con la función registrar_venta (todo o nada).
"""
import uuid
from datetime import timedelta

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from app.db import supabase
from app import utils as U
from app.comprobante import cargar_venta, generar_html

METODOS_PAGO = {
    "Efectivo Bs": "VES",
    "Pago Móvil": "VES",
    "Punto de Venta (Débito/Crédito)": "VES",
    "Transferencia Bs": "VES",
    "Efectivo USD": "USD",
    "Zelle": "USD",
}
REQUIERE_REFERENCIA = {"Pago Móvil", "Punto de Venta (Débito/Crédito)", "Transferencia Bs", "Zelle"}
COLS_PRODUCTO = "id, sku, nombre, marca, precio_usd, stock_actual, exento_iva, activo"


# =====================================================================
# ESTADO
# =====================================================================
def _init_estado():
    ss = st.session_state
    ss.setdefault("pos_carrito", [])
    ss.setdefault("pos_pagos", [])
    ss.setdefault("pos_ver", 0)                       # versión del editor del carrito
    ss.setdefault("pos_key", str(uuid.uuid4()))       # idempotencia de la venta
    ss.setdefault("pos_ultima_venta", None)
    ss.setdefault("pos_mensajes", [])


def _mensaje(tipo: str, texto: str):
    st.session_state.pos_mensajes.append((tipo, texto))


def _mostrar_mensajes():
    for tipo, texto in st.session_state.pos_mensajes:
        {"ok": st.toast, "error": st.error, "warn": st.warning}.get(tipo, st.info)(texto)
    st.session_state.pos_mensajes = []


def _reiniciar_venta():
    ss = st.session_state
    ss.pos_carrito = []
    ss.pos_pagos = []
    ss.pos_ver += 1
    ss.pos_key = str(uuid.uuid4())
    for k in list(ss.keys()):
        if k.startswith("pos_cli_") or k in ("pos_obs", "pos_busqueda"):
            del ss[k]


# =====================================================================
# CARRITO
# =====================================================================
def _agregar(prod: dict, cantidad: int = 1) -> bool:
    ss = st.session_state
    stock = int(prod.get("stock_actual") or 0)
    permitir = U.es_verdadero(ss.get("_pos_cfg", {}).get("permitir_venta_sin_stock"))
    for item in ss.pos_carrito:
        if item["producto_id"] == prod["id"]:
            nueva = item["cantidad"] + cantidad
            if nueva > stock and not permitir:
                _mensaje("warn", f"Stock insuficiente de {prod['sku']}: disponible {stock}.")
                return False
            item["cantidad"] = nueva
            ss.pos_ver += 1
            _mensaje("ok", f"➕ {prod['nombre']} (x{nueva})")
            return True
    if stock < cantidad and not permitir:
        _mensaje("warn", f"{prod['sku']} está agotado (stock {stock}).")
        return False
    ss.pos_carrito.append({
        "producto_id": prod["id"], "sku": prod["sku"], "nombre": prod["nombre"],
        "precio_usd": float(prod["precio_usd"] or 0), "stock": stock,
        "exento_iva": bool(prod.get("exento_iva")), "cantidad": cantidad, "descuento_pct": 0.0,
    })
    ss.pos_ver += 1
    _mensaje("ok", f"➕ {prod['nombre']}")
    return True


def _cb_escaner():
    """Enter en el buscador: si el texto es un SKU exacto, se agrega directo (lector de código de barras)."""
    texto = st.session_state.get("pos_busqueda", "").strip()
    if not texto:
        return
    try:
        res = (supabase.table("productos").select(COLS_PRODUCTO)
               .in_("sku", list({texto, texto.upper()})).eq("activo", True).limit(1).execute())
        if res.data:
            _agregar(res.data[0], 1)
            st.session_state.pos_busqueda = ""
    except Exception as e:
        _mensaje("error", U.mensaje_error(e))


def _buscar(texto: str) -> list[dict]:
    palabras = [p for p in texto.replace(",", " ").replace("(", " ").replace(")", " ").split() if p]
    if not palabras:
        return []
    p0 = palabras[0]
    res = (supabase.table("productos").select(COLS_PRODUCTO)
           .or_(f"sku.ilike.%{p0}%,nombre.ilike.%{p0}%,marca.ilike.%{p0}%")
           .eq("activo", True).order("nombre").limit(40).execute())
    datos = res.data or []
    resto = [p.lower() for p in palabras[1:]]
    if resto:
        datos = [d for d in datos
                 if all(p in f"{d['sku']} {d['nombre']} {d.get('marca') or ''}".lower() for p in resto)]
    return datos[:12]


def _seccion_busqueda(tasa):
    st.markdown("#### 🔍 Agregar productos")
    st.text_input(
        "SKU, nombre o marca",
        key="pos_busqueda",
        on_change=_cb_escaner,
        placeholder="Escanea el código o escribe y presiona Enter (ej: h4 led)",
        label_visibility="collapsed",
    )
    texto = st.session_state.get("pos_busqueda", "").strip()
    if not texto:
        return
    try:
        resultados = _buscar(texto)
    except Exception as e:
        st.error(f"Error en la búsqueda: {U.mensaje_error(e)}")
        return
    if not resultados:
        st.caption("Sin resultados.")
        return
    for p in resultados:
        stock = int(p.get("stock_actual") or 0)
        c1, c2, c3, c4 = st.columns([5, 2, 2, 1])
        c1.markdown(f"`{p['sku']}` **{p['nombre']}**" + (f" · {p['marca']}" if p.get("marca") else ""))
        c2.markdown(f"{U.fmt_usd(p['precio_usd'])}<br><small>{U.fmt_bs(U.D(p['precio_usd']) * tasa)}</small>",
                    unsafe_allow_html=True)
        c3.markdown("❌ Agotado" if stock <= 0 else ("⚠️ " if stock <= 3 else "✅ ") + f"{stock} und")
        if c4.button("➕", key=f"pos_add_{p['id']}", disabled=stock <= 0 and not U.es_verdadero(
                st.session_state._pos_cfg.get("permitir_venta_sin_stock"))):
            _agregar(p, 1)
            st.rerun()


def _seccion_carrito(tasa, cfg) -> list[str]:
    """Muestra y edita el carrito. Devuelve la lista de problemas que impiden facturar."""
    ss = st.session_state
    st.markdown("#### 🛒 Carrito")
    if not ss.pos_carrito:
        st.info("El carrito está vacío. Busca o escanea productos arriba.")
        return ["carrito vacío"]

    desc_max = float(cfg.get("descuento_max_pct", 10))
    df = pd.DataFrame(ss.pos_carrito)
    df["subtotal_usd"] = df.apply(
        lambda r: float(U.r2(U.D(r.precio_usd) * U.D(r.cantidad) * (1 - U.D(r.descuento_pct) / 100))), axis=1)
    df["subtotal_bs"] = df["subtotal_usd"].apply(lambda x: float(U.r2(U.D(x) * tasa)))
    df["quitar"] = False

    editado = st.data_editor(
        df[["sku", "nombre", "stock", "cantidad", "precio_usd", "descuento_pct", "subtotal_usd", "subtotal_bs", "quitar"]],
        key=f"pos_editor_{ss.pos_ver}",
        hide_index=True,
        use_container_width=True,
        disabled=["sku", "nombre", "stock", "precio_usd", "subtotal_usd", "subtotal_bs"],
        column_config={
            "sku": st.column_config.TextColumn("SKU", width="small"),
            "nombre": st.column_config.TextColumn("Producto", width="large"),
            "stock": st.column_config.NumberColumn("Stock", format="%d", width="small"),
            "cantidad": st.column_config.NumberColumn("Cant.", min_value=1, step=1, format="%d", width="small"),
            "precio_usd": st.column_config.NumberColumn("Precio $", format="%.2f"),
            "descuento_pct": st.column_config.NumberColumn("Desc. %", min_value=0.0, max_value=desc_max,
                                                           step=1.0, format="%.0f", width="small"),
            "subtotal_usd": st.column_config.NumberColumn("Subtotal $", format="%.2f"),
            "subtotal_bs": st.column_config.NumberColumn("Subtotal Bs", format="%.2f"),
            "quitar": st.column_config.CheckboxColumn("🗑️", width="small"),
        },
    )

    # Sincronizar cambios del editor con el carrito
    cambio = False
    if editado["quitar"].any():
        ss.pos_carrito = [it for it, q in zip(ss.pos_carrito, editado["quitar"]) if not q]
        ss.pos_ver += 1
        st.rerun()
    for i, fila in editado.iterrows():
        cant = 1 if pd.isna(fila["cantidad"]) else max(int(fila["cantidad"]), 1)
        desc = 0.0 if pd.isna(fila["descuento_pct"]) else float(fila["descuento_pct"])
        if cant != ss.pos_carrito[i]["cantidad"] or desc != ss.pos_carrito[i]["descuento_pct"]:
            ss.pos_carrito[i]["cantidad"] = cant
            ss.pos_carrito[i]["descuento_pct"] = desc
            cambio = True
    if cambio:
        st.rerun()

    if st.button("🧹 Vaciar carrito"):
        ss.pos_carrito = []
        ss.pos_pagos = []
        ss.pos_ver += 1
        st.rerun()

    problemas = []
    if not U.es_verdadero(cfg.get("permitir_venta_sin_stock")):
        for it in ss.pos_carrito:
            if it["cantidad"] > it["stock"]:
                problemas.append(f"{it['sku']}: pides {it['cantidad']} y hay {it['stock']}")
    if problemas:
        st.warning("Stock insuficiente → " + " · ".join(problemas))
    return problemas


# =====================================================================
# CLIENTE
# =====================================================================
def _seccion_cliente() -> tuple[dict | None, str | None]:
    st.markdown("#### 👤 Cliente")
    if st.checkbox("Consumidor final (sin datos)", value=True, key="pos_cli_final"):
        return {"rif": "", "nombre": "CONSUMIDOR FINAL"}, None

    c1, c2 = st.columns([1, 3])
    tipo = c1.selectbox("Tipo", ["V", "E", "J", "G", "P"], key="pos_cli_tipo")
    numero = c2.text_input("Cédula / RIF", key="pos_cli_num", placeholder="12345678 ó 123456789")
    if not numero:
        return None, "Indica la cédula o RIF del cliente."
    rif = U.normalizar_rif(tipo, numero)
    if not rif:
        return None, "Cédula/RIF inválido (5 a 9 dígitos)."

    existente = None
    try:
        res = supabase.table("clientes").select("*").eq("rif", rif).limit(1).execute()
        existente = res.data[0] if res.data else None
    except Exception:
        pass

    st.caption(f"RIF: **{rif}** · " + ("✅ Cliente registrado" if existente else "🆕 Cliente nuevo"))
    nombre = st.text_input("Nombre / Razón social *", value=(existente or {}).get("nombre", ""),
                           key=f"pos_cli_nombre_{rif}")
    c3, c4 = st.columns(2)
    telefono = c3.text_input("Teléfono", value=(existente or {}).get("telefono") or "", key=f"pos_cli_tel_{rif}")
    direccion = c4.text_input("Dirección", value=(existente or {}).get("direccion") or "", key=f"pos_cli_dir_{rif}")
    if not nombre.strip():
        return None, "Indica el nombre del cliente."
    return {"rif": rif, "nombre": nombre.strip(), "telefono": telefono, "direccion": direccion}, None


# =====================================================================
# PAGOS
# =====================================================================
def _cb_agregar_pago(exacto: bool):
    ss = st.session_state
    metodo = ss.pos_pago_metodo
    moneda = METODOS_PAGO[metodo]
    referencia = (ss.get("pos_pago_ref") or "").strip()
    if exacto:
        monto = U.monto_para_completar(ss.pos_carrito, ss.pos_pagos, ss._pos_tasa, ss._pos_cfg, moneda)
    else:
        monto = U.r2(ss.get("pos_pago_monto") or 0)
    if monto <= 0:
        _mensaje("warn", "El monto debe ser mayor que cero (o el pago ya está completo).")
        return
    if metodo in REQUIERE_REFERENCIA and not referencia:
        _mensaje("warn", f"{metodo} requiere número de referencia.")
        return
    ss.pos_pagos.append({"metodo": metodo, "moneda": moneda, "monto": float(monto), "referencia": referencia})
    ss.pos_pago_monto = 0.0
    ss.pos_pago_ref = ""


def _seccion_pagos(tasa, cfg) -> dict:
    ss = st.session_state
    t = U.calcular_totales(ss.pos_carrito, ss.pos_pagos, tasa, cfg)

    st.markdown("#### 💰 Totales")
    filas = [
        ("Exento", t["exento_usd"], t["exento_bs"]),
        ("Base imponible", t["base_usd"], t["base_bs"]),
        (f"IVA {U.fmt_num(t['iva_pct'], 0)}%", t["iva_usd"], t["iva_bs"]),
        ("TOTAL", t["total_usd"], t["total_bs"]),
    ]
    if t["igtf_usd"] > 0:
        filas.append((f"IGTF {U.fmt_num(t['igtf_pct'], 0)}% (s/ divisas)", t["igtf_usd"], t["igtf_bs"]))
        filas.append(("TOTAL A PAGAR", t["total_pagar_usd"], t["total_pagar_bs"]))
    st.dataframe(
        pd.DataFrame([{"Concepto": c, "USD": U.fmt_usd(u), "Bs": U.fmt_bs(b)} for c, u, b in filas]),
        hide_index=True, use_container_width=True,
    )
    c1, c2 = st.columns(2)
    c1.metric("Si paga todo en Bs", U.fmt_bs(t["total_bs"]))
    c2.metric("Si paga todo en divisas", U.fmt_usd(t["total_todo_divisas_usd"]),
              help="Incluye IGTF" if t["igtf_pct"] > 0 else None)

    st.markdown("#### 💳 Pagos")
    c1, c2 = st.columns([3, 2])
    metodo = c1.selectbox("Método", list(METODOS_PAGO), key="pos_pago_metodo")
    moneda = METODOS_PAGO[metodo]
    c2.number_input(f"Monto ({'USD' if moneda == 'USD' else 'Bs'})", min_value=0.0, step=1.0,
                    format="%.2f", key="pos_pago_monto")
    if metodo in REQUIERE_REFERENCIA:
        st.text_input("Referencia *", key="pos_pago_ref", placeholder="Últimos dígitos / N° de aprobación")
    b1, b2 = st.columns(2)
    b1.button("➕ Agregar pago", on_click=_cb_agregar_pago, args=(False,), use_container_width=True)
    b2.button("⚡ Pagar lo que falta", on_click=_cb_agregar_pago, args=(True,), use_container_width=True,
              disabled=t["completo"] or not ss.pos_carrito)

    for i, p in enumerate(ss.pos_pagos):
        c1, c2, c3 = st.columns([4, 3, 1])
        c1.write(f"{p['metodo']}" + (f" · Ref {p['referencia']}" if p["referencia"] else ""))
        c2.write(U.fmt_usd(p["monto"]) if p["moneda"] == "USD" else U.fmt_bs(p["monto"]))
        if c3.button("✖", key=f"pos_delpago_{i}"):
            ss.pos_pagos.pop(i)
            st.rerun()

    if ss.pos_carrito:
        if t["completo"]:
            vuelto = []
            if t["vuelto_usd"] > 0:
                vuelto.append(U.fmt_usd(t["vuelto_usd"]))
            if t["vuelto_bs"] > 0:
                vuelto.append(U.fmt_bs(t["vuelto_bs"]))
            st.success("✅ Pago completo" + (f" · **Vuelto: {' + '.join(vuelto)}**" if vuelto else ""))
        else:
            falta_usd = U.monto_para_completar(ss.pos_carrito, ss.pos_pagos, tasa, cfg, "USD")
            st.warning(f"Falta: **{U.fmt_bs(t['falta_bs'])}** ó **{U.fmt_usd(falta_usd)}** en divisas")
    return t


# =====================================================================
# FINALIZAR
# =====================================================================
def _finalizar(cliente: dict):
    ss = st.session_state
    items = [{"producto_id": it["producto_id"], "cantidad": int(it["cantidad"]),
              "descuento_pct": float(it["descuento_pct"])} for it in ss.pos_carrito]
    datos = None
    try:
        res = supabase.rpc("registrar_venta", {
            "p_items": items,
            "p_pagos": ss.pos_pagos,
            "p_cliente": cliente,
            "p_observaciones": ss.get("pos_obs") or None,
            "p_idempotency_key": ss.pos_key,
        }).execute()
        datos = res.data
    except Exception as e:
        st.error(f"❌ No se pudo registrar la venta: {U.mensaje_error(e)}")
        return
    ss.pos_ultima_venta = datos["venta_id"]
    _reiniciar_venta()
    _mensaje("ok", f"✅ Venta {datos['numero']} registrada")
    st.rerun()


def _panel_ultima_venta(cfg):
    ss = st.session_state
    try:
        venta, detalle, pagos = cargar_venta(supabase, ss.pos_ultima_venta)
    except Exception as e:
        st.error(U.mensaje_error(e))
        ss.pos_ultima_venta = None
        return
    st.success(f"### ✅ Venta {venta['numero']} registrada — {U.fmt_usd(venta['total_pagar_usd'])} · "
               f"{U.fmt_bs(venta['total_pagar_bs'])}")
    html = generar_html(venta, detalle, pagos, cfg)
    c1, c2 = st.columns([1, 1])
    with c1:
        components.html(html, height=720, scrolling=True)
    with c2:
        st.download_button("⬇️ Descargar comprobante (HTML)", html.encode("utf-8"),
                           file_name=f"{venta['numero']}.html", mime="text/html", use_container_width=True)
        if st.button("🛒 Nueva venta", type="primary", use_container_width=True):
            ss.pos_ultima_venta = None
            st.rerun()


def _tab_nueva_venta(tasa, cfg):
    ss = st.session_state
    if ss.pos_ultima_venta:
        _panel_ultima_venta(cfg)
        return

    izq, der = st.columns([3, 2], gap="large")
    with izq:
        _seccion_busqueda(tasa)
        st.divider()
        problemas = _seccion_carrito(tasa, cfg)
    with der:
        cliente, error_cliente = _seccion_cliente()
        st.divider()
        totales = _seccion_pagos(tasa, cfg)
        st.text_input("Observaciones (opcional)", key="pos_obs")

        bloqueos = list(problemas)
        if error_cliente:
            bloqueos.append(error_cliente)
            st.caption(f"⚠️ {error_cliente}")
        if not totales["completo"]:
            bloqueos.append("pago incompleto")
        if st.button("💳 FINALIZAR VENTA", type="primary", use_container_width=True, disabled=bool(bloqueos)):
            _finalizar(cliente)


# =====================================================================
# HISTORIAL / CIERRE / ANULACIÓN
# =====================================================================
def _tab_historial(cfg):
    st.markdown("#### 📄 Ventas registradas")
    hoy = U.hoy_vzla()
    c1, c2, c3, c4 = st.columns([2, 2, 2, 3])
    desde = c1.date_input("Desde", hoy, key="hist_desde", format="DD/MM/YYYY")
    hasta = c2.date_input("Hasta", hoy, key="hist_hasta", format="DD/MM/YYYY")
    estado = c3.selectbox("Estado", ["Todas", "EMITIDA", "ANULADA"], key="hist_estado")
    texto = c4.text_input("Buscar N° o cliente", key="hist_texto")

    if hasta < desde:
        st.warning("La fecha 'Hasta' es anterior a 'Desde'.")
        return
    if (hasta - desde) > timedelta(days=366):
        st.warning("Consulta máximo un año.")
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
        st.info("No hay ventas en el período.")
        return

    emitidas = [v for v in ventas if v["estado"] == "EMITIDA"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Ventas emitidas", len(emitidas))
    m2.metric("Total USD", U.fmt_usd(sum(U.D(v["total_usd"]) for v in emitidas)))
    m3.metric("Total Bs", U.fmt_bs(sum(U.D(v["total_bs"]) for v in emitidas)))
    m4.metric("IGTF percibido", U.fmt_usd(sum(U.D(v["igtf_usd"]) for v in emitidas)))

    tabla = pd.DataFrame([{
        "N°": v["numero"], "Fecha": U.fecha_hora_local(v["fecha"]), "Cliente": v["cliente_nombre"],
        "RIF": v["cliente_rif"], "Total $": float(v["total_pagar_usd"]), "Total Bs": float(v["total_pagar_bs"]),
        "Tasa": float(v["tasa_bcv"]), "Estado": v["estado"], "Usuario": v.get("usuario_email") or "",
    } for v in ventas])
    st.dataframe(tabla, hide_index=True, use_container_width=True, column_config={
        "Total $": st.column_config.NumberColumn(format="%.2f"),
        "Total Bs": st.column_config.NumberColumn(format="%.2f"),
        "Tasa": st.column_config.NumberColumn(format="%.4f"),
    })
    st.download_button("⬇️ Exportar a CSV", tabla.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"ventas_{desde}_{hasta}.csv", mime="text/csv")

    # --- Resumen de caja por método de pago ---
    with st.expander("💵 Cierre de caja del período (por método de pago)"):
        ids = [v["id"] for v in emitidas]
        if ids:
            pagos = []
            for i in range(0, len(ids), 200):
                pagos += supabase.table("pagos_venta").select("metodo, moneda, monto").in_(
                    "venta_id", ids[i:i + 200]).execute().data or []
            vuelto_usd = sum(U.D(v["vuelto_usd"]) for v in emitidas)
            vuelto_bs = sum(U.D(v["vuelto_bs"]) for v in emitidas)
            df = pd.DataFrame(pagos)
            resumen = df.groupby(["metodo", "moneda"], as_index=False)["monto"].sum()
            resumen["monto"] = resumen.apply(
                lambda r: U.fmt_usd(r.monto) if r.moneda == "USD" else U.fmt_bs(r.monto), axis=1)
            st.dataframe(resumen.rename(columns={"metodo": "Método", "moneda": "Moneda", "monto": "Recibido"}),
                         hide_index=True, use_container_width=True)
            st.caption(f"Vueltos entregados: {U.fmt_usd(vuelto_usd)} y {U.fmt_bs(vuelto_bs)} "
                       "(réstalos del efectivo recibido al cuadrar caja).")
        else:
            st.info("Sin ventas emitidas.")

    # --- Detalle / reimpresión / anulación ---
    st.markdown("#### 🔎 Ver / reimprimir / anular")
    opciones = {f"{v['numero']} · {v['cliente_nombre']} · {U.fmt_usd(v['total_pagar_usd'])} · {v['estado']}": v["id"]
                for v in ventas}
    sel = st.selectbox("Selecciona una venta", list(opciones), key="hist_sel")
    if not sel:
        return
    venta, detalle, pagos = cargar_venta(supabase, opciones[sel])
    html = generar_html(venta, detalle, pagos, cfg)
    c1, c2 = st.columns([1, 1])
    with c1:
        components.html(html, height=700, scrolling=True)
    with c2:
        st.download_button("⬇️ Descargar comprobante", html.encode("utf-8"),
                           file_name=f"{venta['numero']}.html", mime="text/html", use_container_width=True)
        if venta["estado"] == "ANULADA":
            st.error(f"Anulada el {U.fecha_hora_local(venta['anulada_at'])}: {venta['motivo_anulacion']}")
        elif not U.es_admin(cfg, _email_usuario()):
            st.info("Solo un administrador puede anular ventas.")
        else:
            with st.expander("↩️ Anular esta venta"):
                st.caption("Reingresa el stock y genera una nota de crédito con la **tasa BCV de la venta original** "
                           f"(Bs. {U.fmt_num(venta['tasa_bcv'], 4)}).")
                motivo = st.text_area("Motivo (mínimo 10 caracteres)", key=f"anular_motivo_{venta['id']}")
                seguro = st.checkbox("Confirmo que deseo anular esta venta", key=f"anular_ok_{venta['id']}")
                if st.button("Anular venta", type="primary", disabled=not seguro, key=f"anular_btn_{venta['id']}"):
                    try:
                        r = supabase.rpc("anular_venta", {"p_venta_id": venta["id"], "p_motivo": motivo}).execute()
                    except Exception as e:
                        st.error(U.mensaje_error(e))
                    else:
                        _mensaje("ok", f"Venta anulada. Nota de crédito {r.data['nota_credito']}")
                        st.rerun()


def _email_usuario():
    u = st.session_state.get("usuario")
    return getattr(u, "email", None) if u else None


# =====================================================================
# RENDER
# =====================================================================
def render():
    _init_estado()
    st.title("🛒 Punto de Venta")

    cfg = U.obtener_config(supabase)
    fecha_tasa, tasa = U.tasa_vigente(supabase)
    st.session_state._pos_cfg = cfg
    st.session_state._pos_tasa = tasa

    if not tasa:
        st.error("⚠️ No hay tasa BCV registrada (o falta ejecutar el script SQL de la Fase 3). "
                 "Ve al módulo **Tasa BCV**.")
        return

    dias = (U.hoy_vzla() - fecha_tasa).days
    dias_max = int(cfg.get("tasa_dias_max", 4))
    texto_tasa = f"💱 Tasa BCV aplicada: **Bs. {U.fmt_num(tasa, 4)}** · fecha valor {fecha_tasa:%d/%m/%Y}"
    if dias > dias_max:
        st.error(texto_tasa + f" — tiene {dias} días. Actualízala para poder vender.")
    elif dias > 0 and U.hoy_vzla().weekday() < 5:
        st.warning(texto_tasa + " — no hay tasa con fecha de hoy. Verifica en bcv.org.ve.")
    else:
        st.info(texto_tasa)
    if U.es_verdadero(cfg.get("igtf_activo")):
        st.caption(f"IGTF {cfg.get('igtf_porcentaje')}% activo sobre pagos en divisas (Contribuyente Especial).")

    _mostrar_mensajes()

    tab_venta, tab_hist = st.tabs(["🛒 Nueva venta", "📄 Historial y cierre"])
    with tab_venta:
        _tab_nueva_venta(tasa, cfg)
    with tab_hist:
        _tab_historial(cfg)
