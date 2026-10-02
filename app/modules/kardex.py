"""KARDEX · historial de entradas y salidas con tasa BCV y equivalente en Bs."""
from datetime import timedelta

import pandas as pd
import streamlit as st

from app.db import supabase
from app import utils as U

MOTIVOS = {
    "COMPRA": "📥 Compra",
    "VENTA": "🛒 Venta",
    "ANULACION_VENTA": "↩️ Anulación de venta",
    "ANULACION_COMPRA": "↩️ Anulación de compra",
    "INVENTARIO_INICIAL": "🆕 Inventario inicial",
    "AJUSTE_MANUAL": "✏️ Ajuste manual",
}


def _productos() -> list[dict]:
    try:
        return (supabase.table("productos").select("id, sku, nombre, stock_actual, costo_usd, precio_usd")
                .order("nombre").limit(5000).execute().data or [])
    except Exception:
        return []


def _movimientos(desde, hasta, producto_id=None, motivo=None) -> list[dict]:
    ini, fin = U.rango_dia_iso(desde, hasta)
    q = (supabase.table("movimientos_inventario").select("*")
         .gte("fecha", ini).lte("fecha", fin).order("fecha").order("id"))
    if producto_id:
        q = q.eq("producto_id", producto_id)
    if motivo:
        q = q.eq("motivo", motivo)
    return q.limit(5000).execute().data or []


def _tabla(movs: list[dict], nombres: dict | None = None) -> pd.DataFrame:
    filas = []
    for m in movs:
        signo = 1 if m["tipo"] == "ENTRADA" else -1
        fila = {"Fecha": U.fecha_hora_local(m["fecha"])}
        if nombres is not None:
            fila["Producto"] = nombres.get(m["producto_id"], m["producto_id"])
        fila.update({
            "Movimiento": MOTIVOS.get(m["motivo"], m["motivo"]),
            "Documento": m.get("observacion") or "",
            "Cantidad": float(m["cantidad"]) * signo,
            "Stock antes": float(m["stock_anterior"]),
            "Stock después": float(m["stock_nuevo"]),
            "Costo $": float(m["costo_unitario_usd"] or 0),
            "Tasa BCV": float(m["tasa_bcv"] or 0),
            "Total Bs": float(m["costo_total_bs"] or 0) * signo,
        })
        filas.append(fila)
    return pd.DataFrame(filas)


CONFIG_COLS = {
    "Cantidad": st.column_config.NumberColumn(format="%+.0f"),
    "Stock antes": st.column_config.NumberColumn(format="%.0f"),
    "Stock después": st.column_config.NumberColumn(format="%.0f"),
    "Costo $": st.column_config.NumberColumn(format="%.2f"),
    "Tasa BCV": st.column_config.NumberColumn(format="%.4f"),
    "Total Bs": st.column_config.NumberColumn(format="%.2f"),
}


def _por_producto():
    productos = _productos()
    if not productos:
        st.info("No hay productos.")
        return
    por_id = {p["id"]: p for p in productos}
    hoy = U.hoy_vzla()
    c1, c2, c3 = st.columns([4, 2, 2])
    pid = c1.selectbox("Producto", list(por_id), index=None, placeholder="🔍 Escribe para buscar el producto…",
                       format_func=lambda i: f"{por_id[i]['sku']} · {por_id[i]['nombre']}", key="kx_prod")
    desde = c2.date_input("Desde", hoy - timedelta(days=90), key="kx_desde", format="DD/MM/YYYY")
    hasta = c3.date_input("Hasta", hoy, key="kx_hasta", format="DD/MM/YYYY")
    if not pid:
        st.info("Elige un producto para ver su historial completo: compras, ventas, ajustes y anulaciones.")
        return
    if hasta < desde:
        st.warning("La fecha 'Hasta' es anterior a 'Desde'.")
        return

    p = por_id[pid]
    try:
        movs = _movimientos(desde, hasta, producto_id=pid)
    except Exception as e:
        st.error(U.mensaje_error(e))
        return

    entradas = sum(float(m["cantidad"]) for m in movs if m["tipo"] == "ENTRADA")
    salidas = sum(float(m["cantidad"]) for m in movs if m["tipo"] == "SALIDA")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Stock actual", U.fmt_num(p["stock_actual"] or 0, 0))
    m2.metric("Entradas", f"+{U.fmt_num(entradas, 0)}")
    m3.metric("Salidas", f"−{U.fmt_num(salidas, 0)}")
    m4.metric("Costo actual", U.fmt_usd(p.get("costo_usd")))
    margen = U.margen_pct(p.get("precio_usd"), p.get("costo_usd"))
    m5.metric("Margen", f"{U.fmt_num(margen, 1)} %" if margen is not None else "—",
              help=f"Precio de venta {U.fmt_usd(p.get('precio_usd'))}")

    if not movs:
        st.info("Sin movimientos en el período.")
        return
    df = _tabla(movs)
    st.dataframe(df, hide_index=True, use_container_width=True, column_config=CONFIG_COLS)

    graf = pd.DataFrame({"Fecha": pd.to_datetime([m["fecha"] for m in movs], utc=True).tz_convert(U.TZ),
                         "Stock": [float(m["stock_nuevo"]) for m in movs]}).set_index("Fecha")
    st.caption("Evolución del stock")
    st.line_chart(graf, height=200)

    compras = [m for m in movs if m["motivo"] == "COMPRA"]
    if compras:
        st.caption("Evolución del costo de compra (USD)")
        st.line_chart(pd.DataFrame({
            "Fecha": pd.to_datetime([m["fecha"] for m in compras], utc=True).tz_convert(U.TZ),
            "Costo $": [float(m["costo_unitario_usd"]) for m in compras]}).set_index("Fecha"), height=180)

    st.download_button("⬇️ Descargar kardex (CSV)", df.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"kardex_{p['sku']}_{desde}_{hasta}.csv", mime="text/csv", on_click="ignore")


def _general():
    hoy = U.hoy_vzla()
    c1, c2, c3 = st.columns([2, 2, 3])
    desde = c1.date_input("Desde", hoy - timedelta(days=7), key="kg_desde", format="DD/MM/YYYY")
    hasta = c2.date_input("Hasta", hoy, key="kg_hasta", format="DD/MM/YYYY")
    motivo = c3.selectbox("Tipo de movimiento", [None] + list(MOTIVOS), key="kg_motivo",
                          format_func=lambda m: "Todos" if m is None else MOTIVOS[m])
    if hasta < desde or (hasta - desde) > timedelta(days=366):
        st.warning("Revisa el rango de fechas (máximo un año).")
        return
    try:
        movs = _movimientos(desde, hasta, motivo=motivo)
    except Exception as e:
        st.error(U.mensaje_error(e))
        return
    if not movs:
        st.info("Sin movimientos en el período.")
        return
    nombres = {p["id"]: f"{p['sku']} · {p['nombre']}" for p in _productos()}

    ent = [m for m in movs if m["tipo"] == "ENTRADA"]
    sal = [m for m in movs if m["tipo"] == "SALIDA"]
    m1, m2, m3 = st.columns(3)
    m1.metric("Movimientos", len(movs))
    m2.metric("Unidades que entraron", U.fmt_num(sum(float(m["cantidad"]) for m in ent), 0))
    m3.metric("Unidades que salieron", U.fmt_num(sum(float(m["cantidad"]) for m in sal), 0))

    df = _tabla(list(reversed(movs)), nombres)
    st.dataframe(df, hide_index=True, use_container_width=True, column_config=CONFIG_COLS)
    st.download_button("⬇️ Descargar (CSV)", df.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"movimientos_{desde}_{hasta}.csv", mime="text/csv", on_click="ignore")
    if len(movs) >= 5000:
        st.caption("Se muestran los primeros 5.000 movimientos. Reduce el rango de fechas para ver el resto.")


def render():
    st.title("📒 Kardex")
    st.caption("Cada entrada y salida de inventario, con el costo en USD, la tasa BCV aplicada y su equivalente en Bs.")
    tab1, tab2 = st.tabs(["📦 Por producto", "📋 Todos los movimientos"])
    with tab1:
        _por_producto()
    with tab2:
        _general()
