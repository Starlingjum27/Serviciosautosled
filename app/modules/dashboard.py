"""
DASHBOARD · Servicios Autos LED
Panel ejecutivo: tasa BCV, ventas, utilidad, inventario, compras, reposición y tendencias.
"""
from datetime import datetime, timedelta
from html import escape

import altair as alt
import pandas as pd
import streamlit as st

from app.db import supabase
from app import utils as U

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
PALETA = ["#00d4ff", "#7c3aed", "#22c55e", "#f59e0b", "#ef4444", "#ec4899", "#14b8a6"]

CSS = """
<style>
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:18px !important;}
.db-hero {display:flex; justify-content:space-between; align-items:stretch; gap:1.2rem; flex-wrap:wrap;
  padding:1.6rem 1.8rem; border-radius:22px; color:#f8fafc; margin-bottom:1rem;
  background:radial-gradient(circle at 0% 0%, rgba(0,212,255,.28), transparent 45%),
             radial-gradient(circle at 100% 100%, rgba(124,58,237,.35), transparent 50%),
             linear-gradient(135deg,#0b1224 0%,#1e1b4b 100%);
  border:1px solid rgba(255,255,255,.08); box-shadow:0 14px 34px rgba(0,0,0,.28);}
.db-hello {font-size:.95rem; opacity:.8;}
.db-brand {font-size:2rem; font-weight:800; line-height:1.15; margin:.15rem 0 .35rem 0; letter-spacing:-.02em;}
.db-brand span {background:linear-gradient(90deg,#00d4ff,#a78bfa); -webkit-background-clip:text;
  background-clip:text; color:transparent;}
.db-date {font-size:.9rem; opacity:.75;}
.db-tasa {min-width:260px; padding:1rem 1.2rem; border-radius:16px; background:rgba(255,255,255,.07);
  border:1px solid rgba(255,255,255,.14); backdrop-filter:blur(8px);}
.db-tasa .t1 {font-size:.75rem; text-transform:uppercase; letter-spacing:.08em; opacity:.75;}
.db-tasa .t2 {font-size:2.1rem; font-weight:800; line-height:1.15;
  background:linear-gradient(90deg,#ffffff,#7dd3fc); -webkit-background-clip:text; background-clip:text; color:transparent;}
.db-tasa .t3 {font-size:.8rem; opacity:.8; margin-top:.2rem;}
.db-grid {display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:1rem; margin:.4rem 0 1.2rem 0;}
.db-kpi {position:relative; overflow:hidden; padding:1.1rem 1.2rem 1rem 1.2rem; border-radius:18px;
  background:linear-gradient(145deg, rgba(128,128,128,.08), rgba(128,128,128,.02));
  border:1px solid rgba(128,128,128,.22); transition:transform .18s ease, box-shadow .18s ease;}
.db-kpi:hover {transform:translateY(-3px); box-shadow:0 14px 26px rgba(0,0,0,.18);}
.db-kpi:before {content:""; position:absolute; left:0; right:0; top:0; height:4px; background:var(--acc);}
.db-kpi:after {content:""; position:absolute; right:-40px; top:-40px; width:120px; height:120px; border-radius:50%;
  background:var(--acc); opacity:.08;}
.db-top {display:flex; justify-content:space-between; align-items:center;}
.db-ico {width:42px; height:42px; border-radius:12px; display:flex; align-items:center; justify-content:center;
  font-size:1.3rem; background:var(--soft);}
.db-lbl {font-size:.74rem; text-transform:uppercase; letter-spacing:.07em; opacity:.7; margin-top:.75rem;}
.db-val {font-size:1.7rem; font-weight:800; line-height:1.2; letter-spacing:-.01em;}
.db-sub {font-size:.82rem; opacity:.72; margin-top:.1rem;}
.db-chip {display:inline-block; padding:.15rem .55rem; border-radius:999px; font-size:.74rem; font-weight:700;}
.db-up {background:rgba(34,197,94,.16); color:#22c55e;}
.db-down {background:rgba(239,68,68,.16); color:#ef4444;}
.db-flat {background:rgba(148,163,184,.18); color:#94a3b8;}
.db-warn {background:rgba(245,158,11,.18); color:#f59e0b;}
.db-h {font-weight:700; font-size:1.05rem; margin:.1rem 0 .1rem 0;}
.db-hs {font-size:.8rem; opacity:.65; margin-bottom:.6rem;}
.db-row {display:flex; justify-content:space-between; align-items:center; gap:.8rem; padding:.55rem 0;
  border-bottom:1px solid rgba(128,128,128,.15);}
.db-row:last-child {border-bottom:none;}
.db-row .n {font-weight:600; font-size:.9rem;}
.db-row .s {font-size:.76rem; opacity:.65;}
.db-row .r {text-align:right; white-space:nowrap;}
.db-bar {height:6px; border-radius:99px; background:rgba(128,128,128,.2); margin-top:.3rem; overflow:hidden; width:120px;}
.db-bar div {height:100%; border-radius:99px;}
.db-empty {padding:1.2rem; text-align:center; opacity:.6; font-size:.9rem;}
</style>
"""


def _h(html: str) -> str:
    """Quita sangrías y líneas vacías: así Markdown no convierte el HTML en bloque de código."""
    return "\n".join(l.strip() for l in html.splitlines() if l.strip())


def _fecha_local(valor) -> "datetime.date":
    return datetime.fromisoformat(str(valor).replace("Z", "+00:00")).astimezone(U.TZ).date()


def _variacion(actual, anterior) -> str:
    actual, anterior = U.D(actual), U.D(anterior)
    if anterior <= 0:
        return "<span class='db-chip db-flat'>— sin referencia</span>" if actual <= 0 else \
               "<span class='db-chip db-up'>▲ nuevo</span>"
    pct = (actual - anterior) / anterior * 100
    if abs(pct) < 0.05:
        return "<span class='db-chip db-flat'>= igual</span>"
    clase, flecha = ("db-up", "▲") if pct > 0 else ("db-down", "▼")
    return f"<span class='db-chip {clase}'>{flecha} {U.fmt_num(abs(pct), 1)}%</span>"


def _kpi(icono, etiqueta, valor, sub, chip, acc, soft) -> str:
    return f"""
    <div class="db-kpi" style="--acc:{acc}; --soft:{soft};">
      <div class="db-top"><div class="db-ico">{icono}</div>{chip}</div>
      <div class="db-lbl">{etiqueta}</div>
      <div class="db-val">{valor}</div>
      <div class="db-sub">{sub}</div>
    </div>"""


# =====================================================================
# DATOS
# =====================================================================
def _consultar(tabla, columnas, desde_iso=None, filtros=None, limite=5000):
    try:
        q = supabase.table(tabla).select(columnas)
        if desde_iso:
            q = q.gte("fecha", desde_iso)
        for campo, valor in (filtros or {}).items():
            q = q.eq(campo, valor)
        return q.limit(limite).execute().data or []
    except Exception:
        return []


def _en_lotes(tabla, columnas, campo, ids):
    datos = []
    for i in range(0, len(ids), 200):
        try:
            datos += supabase.table(tabla).select(columnas).in_(campo, ids[i:i + 200]).execute().data or []
        except Exception:
            pass
    return datos


def _cargar():
    hoy = U.hoy_vzla()
    inicio = min(hoy.replace(day=1), hoy - timedelta(days=29))
    ini_iso, _ = U.rango_dia_iso(inicio, hoy)
    ventas = _consultar("ventas", "id, numero, fecha, cliente_nombre, total_usd, total_bs, tasa_bcv, estado",
                        ini_iso, {"estado": "EMITIDA"})
    for v in ventas:
        v["dia"] = _fecha_local(v["fecha"])
    recientes = []
    try:
        recientes = (supabase.table("ventas").select("numero, fecha, cliente_nombre, total_pagar_usd, total_pagar_bs, estado")
                     .order("fecha", desc=True).limit(6).execute().data or [])
    except Exception:
        pass
    mes_ids = [v["id"] for v in ventas if v["dia"] >= hoy.replace(day=1)]
    detalle = _en_lotes("detalle_ventas", "venta_id, sku, descripcion, cantidad, subtotal_usd, costo_unitario_usd",
                        "venta_id", mes_ids)
    pagos = _en_lotes("pagos_venta", "venta_id, metodo, moneda, monto", "venta_id", mes_ids)
    productos = _consultar("productos", "sku, nombre, stock_actual, stock_minimo, costo_usd, precio_usd, activo")
    ini_mes, _ = U.rango_dia_iso(hoy.replace(day=1), hoy)
    compras = _consultar("compras", "total_usd, fecha", ini_mes, {"estado": "REGISTRADA"})
    tasas = []
    try:
        tasas = (supabase.table("tasas_bcv").select("fecha, tasa").order("fecha", desc=True)
                 .limit(30).execute().data or [])
    except Exception:
        pass
    return hoy, ventas, recientes, detalle, pagos, productos, compras, tasas


# =====================================================================
# SECCIONES
# =====================================================================
def _hero(hoy, tasas):
    usuario = st.session_state.get("usuario")
    email = getattr(usuario, "email", "") or ""
    meta = getattr(usuario, "user_metadata", None) or {}
    nombre = meta.get("nombre") or meta.get("full_name") or email.split("@")[0].split(".")[0].capitalize()
    hora = U.ahora_vzla().hour
    saludo = "Buenos días" if hora < 12 else ("Buenas tardes" if hora < 19 else "Buenas noches")
    fecha_txt = f"{DIAS[hoy.weekday()].capitalize()}, {hoy.day} de {MESES[hoy.month - 1]} de {hoy.year}"

    fecha_tasa, tasa = U.tasa_vigente(supabase)
    if tasa:
        anterior = next((U.D(t["tasa"]) for t in tasas if str(t["fecha"])[:10] < str(fecha_tasa)), None)
        chip = _variacion(tasa, anterior) if anterior else ""
        estado = (st.session_state.get("tasa_auto") or {}).get("estado")
        origen = {"ok": "🟢 Actualizada automáticamente", "al_dia": "🟢 Al día",
                  "fin_semana": "📅 Tasa del último día hábil"}.get(estado, "🟡 Verifica la tasa del día")
        tasa_html = f"""
        <div class="db-tasa">
          <div class="t1">💱 Tasa oficial BCV</div>
          <div class="t2">Bs. {U.fmt_num(tasa, 4)}</div>
          <div class="t3">Fecha valor {fecha_tasa:%d/%m/%Y} &nbsp; {chip}</div>
          <div class="t3">{origen}</div>
        </div>"""
    else:
        tasa_html = """<div class="db-tasa"><div class="t1">💱 Tasa oficial BCV</div>
        <div class="t2">Sin tasa</div><div class="t3">Regístrala en el módulo Tasa BCV</div></div>"""

    st.markdown(_h(f"""
    <div class="db-hero">
      <div>
        <div class="db-hello">{saludo}, {escape(nombre)} 👋</div>
        <div class="db-brand">Servicios <span>Autos LED</span></div>
        <div class="db-date">📅 {fecha_txt} · Panel de control del negocio</div>
      </div>
      {tasa_html}
    </div>"""), unsafe_allow_html=True)
    return tasa


def _ir(pagina):
    st.session_state.nav = pagina


def _accesos():
    c = st.columns(4)
    c[0].button("🛒 Nueva venta", type="primary", use_container_width=True, on_click=_ir, args=("🛒 Punto de Venta",))
    c[1].button("📥 Registrar compra", use_container_width=True, on_click=_ir, args=("📥 Compras",))
    c[2].button("📦 Ver productos", use_container_width=True, on_click=_ir, args=("📦 Productos",))
    c[3].button("📒 Ver kardex", use_container_width=True, on_click=_ir, args=("📒 Kardex",))


def _kpis(hoy, ventas, detalle, productos, compras, tasa):
    ayer = hoy - timedelta(days=1)
    v_hoy = [v for v in ventas if v["dia"] == hoy]
    v_ayer = [v for v in ventas if v["dia"] == ayer]
    v_mes = [v for v in ventas if v["dia"] >= hoy.replace(day=1)]
    usd_hoy = sum(U.D(v["total_usd"]) for v in v_hoy)
    bs_hoy = sum(U.D(v["total_bs"]) for v in v_hoy)
    usd_ayer = sum(U.D(v["total_usd"]) for v in v_ayer)
    usd_mes = sum(U.D(v["total_usd"]) for v in v_mes)
    bs_mes = sum(U.D(v["total_bs"]) for v in v_mes)

    neto = sum(U.D(d["subtotal_usd"]) for d in detalle)
    costo = sum(U.D(d["cantidad"]) * U.D(d["costo_unitario_usd"]) for d in detalle)
    utilidad = neto - costo
    margen = (utilidad / neto * 100) if neto > 0 else U.D(0)
    ticket = (usd_mes / len(v_mes)) if v_mes else U.D(0)

    activos = [p for p in productos if p.get("activo", True)]
    valor_costo = sum(U.D(p.get("stock_actual")) * U.D(p.get("costo_usd")) for p in activos if (p.get("stock_actual") or 0) > 0)
    valor_venta = sum(U.D(p.get("stock_actual")) * U.D(p.get("precio_usd")) for p in activos if (p.get("stock_actual") or 0) > 0)
    agotados = sum(1 for p in activos if (p.get("stock_actual") or 0) <= 0)
    bajos = sum(1 for p in activos if 0 < (p.get("stock_actual") or 0) <= (p.get("stock_minimo") or 0))
    compras_mes = sum(U.D(c["total_usd"]) for c in compras)

    chip_margen = (f"<span class='db-chip {'db-up' if margen >= 25 else 'db-warn'}'>{U.fmt_num(margen, 1)}% margen</span>"
                   if neto > 0 else "<span class='db-chip db-flat'>sin ventas</span>")
    chip_stock = (f"<span class='db-chip db-down'>{agotados} agotados</span>" if agotados else
                  "<span class='db-chip db-up'>✓ todo ok</span>" if not bajos else
                  f"<span class='db-chip db-warn'>{bajos} bajos</span>")
    tarjetas = [
        _kpi("💵", "Ventas de hoy", U.fmt_usd(usd_hoy), f"{U.fmt_bs(bs_hoy)} · {len(v_hoy)} venta(s)",
             _variacion(usd_hoy, usd_ayer) + "<span style='font-size:.7rem;opacity:.6'> vs ayer</span>",
             "linear-gradient(90deg,#00d4ff,#0ea5e9)", "rgba(0,212,255,.15)"),
        _kpi("📈", f"Ventas de {MESES[hoy.month - 1]}", U.fmt_usd(usd_mes), f"{U.fmt_bs(bs_mes)} · {len(v_mes)} venta(s)",
             "", "linear-gradient(90deg,#7c3aed,#a78bfa)", "rgba(124,58,237,.16)"),
        _kpi("💎", "Utilidad bruta del mes", U.fmt_usd(utilidad), f"Ventas netas {U.fmt_usd(neto)} − costo {U.fmt_usd(costo)}",
             chip_margen, "linear-gradient(90deg,#22c55e,#4ade80)", "rgba(34,197,94,.15)"),
        _kpi("🧾", "Ticket promedio", U.fmt_usd(ticket), "Promedio por venta en el mes",
             "", "linear-gradient(90deg,#f59e0b,#fbbf24)", "rgba(245,158,11,.16)"),
        _kpi("🏬", "Inventario a costo", U.fmt_usd(valor_costo),
             f"≈ {U.fmt_bs(valor_costo * tasa)}" if tasa else "", "",
             "linear-gradient(90deg,#14b8a6,#2dd4bf)", "rgba(20,184,166,.15)"),
        _kpi("🏷️", "Inventario a precio de venta", U.fmt_usd(valor_venta),
             f"Ganancia potencial {U.fmt_usd(valor_venta - valor_costo)}", "",
             "linear-gradient(90deg,#ec4899,#f472b6)", "rgba(236,72,153,.15)"),
        _kpi("📥", "Compras del mes", U.fmt_usd(compras_mes), f"{len(compras)} compra(s) a proveedores", "",
             "linear-gradient(90deg,#6366f1,#818cf8)", "rgba(99,102,241,.16)"),
        _kpi("⚠️", "Productos por reponer", f"{agotados + bajos}", f"de {len(activos)} productos activos",
             chip_stock, "linear-gradient(90deg,#ef4444,#f97316)", "rgba(239,68,68,.15)"),
    ]
    st.markdown(_h(f"<div class='db-grid'>{''.join(tarjetas)}</div>"), unsafe_allow_html=True)


def _titulo(texto, sub=""):
    st.markdown(_h(f"<div class='db-h'>{texto}</div><div class='db-hs'>{sub}</div>"), unsafe_allow_html=True)


def _grafico_ventas(hoy, ventas):
    _titulo("📊 Ventas de los últimos 30 días", "Total diario en dólares (incluye IVA)")
    dias = [hoy - timedelta(days=i) for i in range(29, -1, -1)]
    totales = {d: U.D(0) for d in dias}
    cuenta = {d: 0 for d in dias}
    for v in ventas:
        if v["dia"] in totales:
            totales[v["dia"]] += U.D(v["total_usd"])
            cuenta[v["dia"]] += 1
    df = pd.DataFrame({"fecha": pd.to_datetime(dias), "usd": [float(totales[d]) for d in dias],
                       "ventas": [cuenta[d] for d in dias]})
    if df["usd"].sum() == 0:
        st.markdown("<div class='db-empty'>Aún no hay ventas en este período.</div>", unsafe_allow_html=True)
        return
    base = alt.Chart(df).encode(
        x=alt.X("fecha:T", title=None, axis=alt.Axis(format="%d/%m", grid=False, labelAngle=0, tickCount=8)),
        tooltip=[alt.Tooltip("fecha:T", title="Día", format="%d/%m/%Y"),
                 alt.Tooltip("usd:Q", title="Vendido $", format=",.2f"),
                 alt.Tooltip("ventas:Q", title="N° ventas")])
    area = base.mark_area(
        interpolate="monotone", line={"color": "#00d4ff", "strokeWidth": 2.5},
        color=alt.Gradient(gradient="linear", x1=1, x2=1, y1=1, y2=0,
                           stops=[alt.GradientStop(color="rgba(0,212,255,0.02)", offset=0),
                                  alt.GradientStop(color="rgba(0,212,255,0.45)", offset=1)]),
    ).encode(y=alt.Y("usd:Q", title=None, axis=alt.Axis(format="$,.0f", gridOpacity=0.12, domain=False, ticks=False)))
    puntos = base.mark_circle(size=55, color="#7dd3fc").encode(y="usd:Q").transform_filter("datum.usd > 0")
    st.altair_chart((area + puntos).properties(height=270).configure_view(strokeWidth=0),
                    use_container_width=True)


def _grafico_pagos(ventas, pagos):
    _titulo("💳 Formas de pago", "Cobrado en el mes, equivalente en USD")
    tasas = {v["id"]: U.D(v["tasa_bcv"]) for v in ventas}
    acumulado = {}
    for p in pagos:
        usd = U.D(p["monto"]) if p["moneda"] == "USD" else U.D(p["monto"]) / (tasas.get(p["venta_id"]) or 1)
        acumulado[p["metodo"]] = acumulado.get(p["metodo"], U.D(0)) + usd
    if not acumulado:
        st.markdown("<div class='db-empty'>Sin pagos este mes.</div>", unsafe_allow_html=True)
        return
    df = pd.DataFrame([{"metodo": k, "usd": float(round(v, 2))} for k, v in acumulado.items()])
    df["pct"] = df["usd"] / df["usd"].sum()
    graf = alt.Chart(df).mark_arc(innerRadius=62, outerRadius=105, cornerRadius=5, padAngle=0.02).encode(
        theta=alt.Theta("usd:Q"),
        color=alt.Color("metodo:N", scale=alt.Scale(range=PALETA),
                        legend=alt.Legend(orient="bottom", title=None, columns=2, labelLimit=160)),
        tooltip=[alt.Tooltip("metodo:N", title="Método"), alt.Tooltip("usd:Q", title="USD", format=",.2f"),
                 alt.Tooltip("pct:Q", title="Participación", format=".1%")])
    st.altair_chart(graf.properties(height=290).configure_view(strokeWidth=0), use_container_width=True)


def _top_productos(detalle):
    _titulo("🏆 Productos más vendidos", "Top 6 del mes por monto vendido (sin IVA)")
    if not detalle:
        st.markdown("<div class='db-empty'>Sin ventas este mes.</div>", unsafe_allow_html=True)
        return
    df = pd.DataFrame(detalle)
    df["usd"] = df["subtotal_usd"].astype(float)
    df["utilidad"] = df["usd"] - df["cantidad"].astype(float) * df["costo_unitario_usd"].astype(float)
    top = (df.groupby("descripcion", as_index=False)
           .agg(usd=("usd", "sum"), unidades=("cantidad", "sum"), utilidad=("utilidad", "sum"))
           .sort_values("usd", ascending=False).head(6))
    top["producto"] = top["descripcion"].str.slice(0, 32)
    base = alt.Chart(top).encode(
        y=alt.Y("producto:N", sort="-x", title=None, axis=alt.Axis(labelLimit=220, domain=False, ticks=False)),
        x=alt.X("usd:Q", title=None, axis=None),
        tooltip=[alt.Tooltip("descripcion:N", title="Producto"), alt.Tooltip("unidades:Q", title="Unidades"),
                 alt.Tooltip("usd:Q", title="Vendido $", format=",.2f"),
                 alt.Tooltip("utilidad:Q", title="Utilidad $", format=",.2f")])
    barras = base.mark_bar(cornerRadiusEnd=8, height=22).encode(
        color=alt.Color("usd:Q", scale=alt.Scale(range=["#a78bfa", "#7c3aed"]), legend=None))
    textos = base.mark_text(align="left", dx=6, fontWeight="bold").encode(text=alt.Text("usd:Q", format="$,.2f"))
    st.altair_chart((barras + textos).properties(height=270).configure_view(strokeWidth=0), use_container_width=True)


def _reponer(productos):
    _titulo("🚨 Por reponer", "Productos agotados o en su stock mínimo")
    activos = [p for p in productos if p.get("activo", True)]
    lista = sorted([p for p in activos if (p.get("stock_actual") or 0) <= (p.get("stock_minimo") or 0)],
                   key=lambda p: (p.get("stock_actual") or 0))[:7]
    if not lista:
        st.markdown("<div class='db-empty'>✅ Todo el inventario está sobre el mínimo.</div>", unsafe_allow_html=True)
        return
    filas = ""
    for p in lista:
        stock, minimo = int(p.get("stock_actual") or 0), int(p.get("stock_minimo") or 0)
        pct = max(min(stock / (minimo or 1), 1), 0) * 100
        color = "#ef4444" if stock <= 0 else "#f59e0b"
        chip = "<span class='db-chip db-down'>Agotado</span>" if stock <= 0 else \
               f"<span class='db-chip db-warn'>{stock} / mín {minimo}</span>"
        filas += f"""
        <div class="db-row">
          <div><div class="n">{escape(p['nombre'][:38])}</div><div class="s">{escape(p['sku'])}</div>
            <div class="db-bar"><div style="width:{pct:.0f}%; background:{color};"></div></div></div>
          <div class="r">{chip}</div>
        </div>"""
    st.markdown(_h(filas), unsafe_allow_html=True)


def _ultimas(recientes):
    _titulo("🧾 Últimas ventas", "Los 6 movimientos más recientes")
    if not recientes:
        st.markdown("<div class='db-empty'>Aún no hay ventas registradas.</div>", unsafe_allow_html=True)
        return
    filas = ""
    for v in recientes:
        anulada = v["estado"] == "ANULADA"
        chip = "<span class='db-chip db-down'>Anulada</span>" if anulada else ""
        filas += f"""
        <div class="db-row">
          <div><div class="n">{escape(v['cliente_nombre'][:30])} {chip}</div>
            <div class="s">{escape(v['numero'])} · {U.fecha_hora_local(v['fecha'])}</div></div>
          <div class="r"><div class="n" style="{'text-decoration:line-through;opacity:.5' if anulada else ''}">
            {U.fmt_usd(v['total_pagar_usd'])}</div><div class="s">{U.fmt_bs(v['total_pagar_bs'])}</div></div>
        </div>"""
    st.markdown(_h(filas), unsafe_allow_html=True)


def _grafico_tasa(tasas):
    _titulo("💱 Evolución de la tasa BCV", "Últimos registros")
    if len(tasas) < 2:
        st.markdown("<div class='db-empty'>Se necesitan al menos 2 tasas registradas.</div>", unsafe_allow_html=True)
        return
    df = pd.DataFrame(tasas)
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["tasa"] = df["tasa"].astype(float)
    minimo, maximo = df["tasa"].min(), df["tasa"].max()
    margen = max((maximo - minimo) * 0.15, 0.5)
    base = alt.Chart(df).encode(
        x=alt.X("fecha:T", title=None, axis=alt.Axis(format="%d/%m", grid=False, labelAngle=0)),
        y=alt.Y("tasa:Q", title=None, scale=alt.Scale(domain=[minimo - margen, maximo + margen]),
                axis=alt.Axis(format=",.2f", gridOpacity=0.12, domain=False, ticks=False)),
        tooltip=[alt.Tooltip("fecha:T", title="Fecha valor", format="%d/%m/%Y"),
                 alt.Tooltip("tasa:Q", title="Bs/USD", format=",.4f")])
    linea = base.mark_line(interpolate="monotone", strokeWidth=2.5, color="#a78bfa")
    puntos = base.mark_circle(size=45, color="#c4b5fd")
    st.altair_chart((linea + puntos).properties(height=250).configure_view(strokeWidth=0), use_container_width=True)


# =====================================================================
def render():
    st.markdown(CSS, unsafe_allow_html=True)
    with st.spinner("Preparando tu panel..."):
        hoy, ventas, recientes, detalle, pagos, productos, compras, tasas = _cargar()

    tasa = _hero(hoy, tasas)
    estado = (st.session_state.get("tasa_auto") or {})
    if estado.get("estado") in ("error", "revision"):
        st.warning(f"💱 {estado['mensaje']}")
    _accesos()
    _kpis(hoy, ventas, detalle, productos, compras, tasa)

    c1, c2 = st.columns([2, 1], gap="medium")
    with c1, st.container(border=True):
        _grafico_ventas(hoy, ventas)
    with c2, st.container(border=True):
        _grafico_pagos(ventas, pagos)

    c3, c4 = st.columns([3, 2], gap="medium")
    with c3, st.container(border=True):
        _top_productos(detalle)
    with c4, st.container(border=True):
        _reponer(productos)

    c5, c6 = st.columns([2, 3], gap="medium")
    with c5, st.container(border=True):
        _ultimas(recientes)
    with c6, st.container(border=True):
        _grafico_tasa(tasas)
