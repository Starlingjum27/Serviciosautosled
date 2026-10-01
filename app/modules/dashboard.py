import pandas as pd
import streamlit as st

from app.db import supabase
from app import utils as U


def render():
    st.title("📊 Dashboard")
    hoy = U.hoy_vzla()
    st.caption(f"Hoy: {hoy:%d/%m/%Y} (hora de Venezuela)")

    fecha_tasa, tasa = U.tasa_vigente(supabase)
    ini, fin = U.rango_dia_iso(hoy, hoy)

    try:
        ventas_hoy = (supabase.table("ventas").select("id, numero, fecha, cliente_nombre, total_pagar_usd, "
                                                      "total_pagar_bs, igtf_usd, estado")
                      .gte("fecha", ini).lte("fecha", fin).order("fecha", desc=True).execute().data or [])
    except Exception:
        ventas_hoy = []
    emitidas = [v for v in ventas_hoy if v["estado"] == "EMITIDA"]

    try:
        productos = supabase.table("productos").select("sku, nombre, stock_actual, stock_minimo, costo_usd, activo").execute().data or []
    except Exception:
        productos = []
    activos = [p for p in productos if p.get("activo", True)]
    bajos = [p for p in activos if (p.get("stock_actual") or 0) <= (p.get("stock_minimo") or 0)]
    valor_inv = sum(U.D(p.get("stock_actual")) * U.D(p.get("costo_usd")) for p in activos if (p.get("stock_actual") or 0) > 0)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ventas hoy", len(emitidas))
    c2.metric("Vendido hoy (USD)", U.fmt_usd(sum(U.D(v["total_pagar_usd"]) for v in emitidas)))
    c3.metric("Vendido hoy (Bs)", U.fmt_bs(sum(U.D(v["total_pagar_bs"]) for v in emitidas)))
    c4.metric("Tasa BCV vigente", f"Bs. {U.fmt_num(tasa, 4)}" if tasa else "Sin tasa",
              help=f"Fecha valor {fecha_tasa:%d/%m/%Y}" if fecha_tasa else None)

    c5, c6, c7 = st.columns(3)
    c5.metric("Productos activos", len(activos))
    c6.metric("Stock bajo / agotado", len(bajos))
    c7.metric("Inventario a costo", U.fmt_usd(valor_inv),
              help=f"≈ {U.fmt_bs(valor_inv * tasa)}" if tasa else None)

    if not tasa or (hoy - fecha_tasa).days > 0 and hoy.weekday() < 5:
        st.warning("⚠️ La tasa BCV de hoy no está registrada.")

    izq, der = st.columns(2, gap="large")
    with izq:
        st.subheader("🧾 Últimas ventas de hoy")
        if ventas_hoy:
            st.dataframe(pd.DataFrame([{
                "N°": v["numero"], "Hora": U.fecha_hora_local(v["fecha"])[-8:], "Cliente": v["cliente_nombre"],
                "Total $": U.fmt_usd(v["total_pagar_usd"]), "Estado": v["estado"]} for v in ventas_hoy[:10]]),
                hide_index=True, use_container_width=True)
        else:
            st.info("Aún no hay ventas hoy.")
    with der:
        st.subheader("⚠️ Reponer pronto")
        if bajos:
            st.dataframe(pd.DataFrame([{
                "SKU": p["sku"], "Producto": p["nombre"], "Stock": p.get("stock_actual") or 0,
                "Mínimo": p.get("stock_minimo") or 0} for p in sorted(bajos, key=lambda x: x.get("stock_actual") or 0)[:15]]),
                hide_index=True, use_container_width=True)
        else:
            st.success("Todo el inventario está sobre el mínimo.")
