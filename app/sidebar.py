"""
Barra lateral moderna de Servicios Autos LED.
  · Marca con logo
  · Tasa BCV del día siempre visible (con estado de la actualización automática)
  · Menú agrupado por secciones con íconos Material y el módulo activo resaltado
  · Tarjeta del usuario con su rol y botón de cerrar sesión
La página activa se guarda en st.session_state.nav (los accesos rápidos del Dashboard la usan).
"""
import time
from html import escape

import streamlit as st

from app.db import supabase
from app import utils as U

_BTN = '[data-testid="stSidebar"] button[kind="{k}"], [data-testid="stSidebar"] [data-testid="stBaseButton-{k}"]'

CSS = """
<style>
/* ---------- Fondo y estructura ---------- */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0b1224 0%, #121a36 55%, #1e1b4b 100%);
  border-right: 1px solid rgba(255,255,255,.06);
}
[data-testid="stSidebar"] * { color: #e2e8f0; }
[data-testid="stSidebarUserContent"] { padding-top: .6rem; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: .22rem; }
[data-testid="stSidebarNav"] { display: none; }

/* ---------- Marca ---------- */
.sb-brand { display:flex; align-items:center; gap:.75rem; padding:.2rem .1rem 1rem .1rem; }
.sb-logo { width:46px; height:46px; border-radius:14px; display:flex; align-items:center; justify-content:center;
  font-weight:900; font-size:.8rem; letter-spacing:.03em; color:#0b1224 !important;
  background: linear-gradient(135deg, #00d4ff, #a78bfa); box-shadow: 0 0 22px rgba(0,212,255,.45); }
.sb-name { font-weight:800; font-size:1.05rem; line-height:1.1; color:#ffffff !important; }
.sb-tag { font-size:.72rem; color:#94a3b8 !important; margin-top:.15rem; }

/* ---------- Tasa del día ---------- */
.sb-tasa { padding:.65rem .8rem; border-radius:14px; background:rgba(255,255,255,.05);
  border:1px solid rgba(255,255,255,.09); margin-bottom:.3rem; }
.sb-tasa .l { font-size:.66rem; letter-spacing:.12em; text-transform:uppercase; color:#94a3b8 !important; }
.sb-tasa .v { font-size:1.25rem; font-weight:800; color:#ffffff !important; line-height:1.25; }
.sb-tasa .s { font-size:.72rem; color:#94a3b8 !important; display:flex; align-items:center; gap:.35rem; }
.sb-dot { display:inline-block; width:8px; height:8px; border-radius:50%; }
.sb-alerta { font-size:.72rem; color:#fbbf24 !important; margin-top:.35rem; line-height:1.3; }

/* ---------- Grupos ---------- */
.sb-group { font-size:.64rem; letter-spacing:.16em; text-transform:uppercase; font-weight:700;
  color:#64748b !important; margin:.85rem 0 .15rem .6rem; }

/* ---------- Botones del menú ---------- */
[data-testid="stSidebar"] .stButton button {
  width:100%; justify-content:flex-start; border-radius:12px; padding:.5rem .85rem; min-height:2.55rem;
  border:1px solid transparent; transition: all .16s ease; box-shadow:none;
}
[data-testid="stSidebar"] .stButton button > div { justify-content:flex-start; width:100%; gap:.6rem; }
[data-testid="stSidebar"] .stButton button p { font-size:.93rem; }
""" + _BTN.format(k="tertiary") + """ { background:transparent; color:#cbd5e1; }
""" + _BTN.format(k="tertiary").replace(", ", ":hover, ") + """:hover {
  background:rgba(255,255,255,.07); transform:translateX(3px); }
""" + _BTN.format(k="primary") + """ {
  background: linear-gradient(90deg, rgba(0,212,255,.24), rgba(124,58,237,.24));
  border:1px solid rgba(0,212,255,.38); box-shadow: inset 3px 0 0 #00d4ff, 0 6px 20px rgba(0,212,255,.14);
}
""" + _BTN.format(k="primary") + """ p { font-weight:700; color:#ffffff !important; }

/* ---------- Usuario ---------- */
.sb-user { display:flex; align-items:center; gap:.7rem; padding:.7rem; border-radius:14px;
  background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.09); margin-top:1.1rem; }
.sb-avatar { width:40px; height:40px; border-radius:50%; flex-shrink:0; display:flex; align-items:center;
  justify-content:center; font-weight:800; color:#ffffff !important;
  background: linear-gradient(135deg, #7c3aed, #00d4ff); }
.sb-uname { font-weight:700; font-size:.85rem; color:#ffffff !important; overflow:hidden; text-overflow:ellipsis;
  white-space:nowrap; max-width:175px; }
.sb-role { font-size:.7rem; color:#94a3b8 !important; }
""" + _BTN.format(k="secondary") + """ {
  background:rgba(239,68,68,.08); border:1px solid rgba(239,68,68,.30); justify-content:center;
}
""" + _BTN.format(k="secondary") + """ p { color:#fca5a5 !important; font-weight:600; }
""" + _BTN.format(k="secondary").replace(", ", ":hover, ") + """:hover { background:rgba(239,68,68,.20); }
.sb-foot { font-size:.65rem; color:#475569 !important; text-align:center; margin-top:.8rem; }
</style>
"""


def _ir(pagina: str):
    st.session_state.nav = pagina


def _datos_cache():
    """Tasa vigente y configuración, refrescadas cada 60 s para no consultar en cada clic."""
    ss = st.session_state
    cache = ss.get("_sb_cache")
    if not cache or time.time() - cache["t"] > 60:
        fecha, tasa = U.tasa_vigente(supabase)
        cache = {"t": time.time(), "fecha": fecha, "tasa": tasa, "cfg": U.obtener_config(supabase)}
        ss._sb_cache = cache
    return cache


def _marca():
    st.markdown("""
<div class="sb-brand">
  <div class="sb-logo">LED</div>
  <div><div class="sb-name">Servicios Autos LED</div><div class="sb-tag">Sistema de gestión · Autopartes</div></div>
</div>""", unsafe_allow_html=True)


def _tasa(cache):
    estado = (st.session_state.get("tasa_auto") or {}).get("estado")
    tasa, fecha = cache["tasa"], cache["fecha"]
    if not tasa:
        color, texto = "#ef4444", "Sin tasa registrada"
    elif estado in ("error", "revision"):
        color, texto = "#f59e0b", f"Fecha valor {fecha:%d/%m/%Y}"
    elif fecha and (U.hoy_vzla() - fecha).days > 0 and U.hoy_vzla().weekday() < 5:
        color, texto = "#f59e0b", f"Fecha valor {fecha:%d/%m/%Y} · verificar"
    else:
        color, texto = "#22c55e", f"Fecha valor {fecha:%d/%m/%Y}"
    alerta = ""
    if estado in ("error", "revision"):
        alerta = "<div class='sb-alerta'>⚠️ No se actualizó sola. Regístrala en Tasa BCV.</div>"
    valor = f"Bs. {U.fmt_num(tasa, 4)}" if tasa else "—"
    st.markdown(f"""
<div class="sb-tasa">
  <div class="l">Tasa BCV del día</div>
  <div class="v">{valor}</div>
  <div class="s"><span class="sb-dot" style="background:{color}; box-shadow:0 0 8px {color};"></span>{texto}</div>
  {alerta}
</div>""", unsafe_allow_html=True)


def _usuario(cfg):
    usuario = st.session_state.get("usuario")
    email = getattr(usuario, "email", "") or ""
    meta = getattr(usuario, "user_metadata", None) or {}
    nombre = meta.get("nombre") or meta.get("full_name") or email.split("@")[0]
    iniciales = "".join(p[0] for p in nombre.replace(".", " ").replace("_", " ").split()[:2]).upper() or "U"
    rol = "Administrador" if U.es_admin(cfg, email) else "Usuario"
    st.markdown(f"""
<div class="sb-user">
  <div class="sb-avatar">{escape(iniciales)}</div>
  <div style="min-width:0"><div class="sb-uname">{escape(nombre)}</div>
  <div class="sb-role">{rol} · {escape(email)}</div></div>
</div>""", unsafe_allow_html=True)


def render(menu: list, por_defecto: str, al_cerrar) -> str:
    """
    menu: [(grupo, [(clave, etiqueta, icono_material), ...]), ...]
    Devuelve la clave de la página activa.
    """
    ss = st.session_state
    claves = [c for _, items in menu for c, _, _ in items]
    if ss.get("nav") not in claves:
        ss.nav = por_defecto
    cache = _datos_cache()

    with st.sidebar:
        st.markdown(CSS, unsafe_allow_html=True)
        _marca()
        _tasa(cache)
        for grupo, items in menu:
            st.markdown(f"<div class='sb-group'>{grupo}</div>", unsafe_allow_html=True)
            for clave, etiqueta, icono in items:
                st.button(etiqueta, key=f"sb_{clave}", icon=icono, use_container_width=True,
                          type="primary" if ss.nav == clave else "tertiary",
                          on_click=_ir, args=(clave,))
        _usuario(cache["cfg"])
        if st.button("Cerrar sesión", key="sb_logout", icon=":material/logout:", use_container_width=True):
            al_cerrar()
        st.markdown("<div class='sb-foot'>Servicios Autos LED · v1.0</div>", unsafe_allow_html=True)
    return ss.nav
