import streamlit as st

# 1. Configuración de la página (DEBE ser el primer comando de Streamlit)
st.set_page_config(
    page_title="Servicios Autos Led - Sistema de Inventario",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

from app.db import supabase, reset_client  # noqa: E402
from app import sidebar  # noqa: E402
from app.modules import (  # noqa: E402
    dashboard, productos, tasa_bcv, ventas, configuracion, proveedores, compras, kardex,
)

# 2. Estado de sesión
st.session_state.setdefault("autenticado", False)
st.session_state.setdefault("usuario", None)


def login():
    st.title("🔐 Iniciar Sesión")
    st.markdown("Sistema Profesional de Inventario y Ventas - Autopartes")
    with st.form("login_form"):
        email = st.text_input("Correo Electrónico")
        password = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Ingresar")
    if submit:
        try:
            res = supabase.auth.sign_in_with_password({"email": email.strip(), "password": password})
        except Exception:
            st.error("Correo o contraseña incorrectos.")
            return
        st.session_state.autenticado = True
        st.session_state.usuario = res.user
        st.rerun()


def cerrar_sesion():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    reset_client()
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()


# (clave interna, etiqueta visible, ícono) agrupados por sección
MENU = [
    ("Principal", [
        ("📊 Dashboard", "Dashboard", ":material/space_dashboard:"),
    ]),
    ("Operaciones", [
        ("🛒 Punto de Venta", "Punto de venta", ":material/point_of_sale:"),
        ("📥 Compras", "Compras", ":material/shopping_cart:"),
    ]),
    ("Inventario", [
        ("📦 Productos", "Productos", ":material/inventory_2:"),
        ("🏭 Proveedores", "Proveedores", ":material/local_shipping:"),
        ("📒 Kardex", "Kardex", ":material/receipt_long:"),
    ]),
    ("Sistema", [
        ("💱 Tasa BCV", "Tasa BCV", ":material/currency_exchange:"),
        ("⚙️ Configuración", "Configuración", ":material/settings:"),
    ]),
]

PAGINAS = {
    "📊 Dashboard": dashboard.render,
    "🛒 Punto de Venta": ventas.render,
    "📥 Compras": compras.render,
    "📦 Productos": productos.render,
    "🏭 Proveedores": proveedores.render,
    "📒 Kardex": kardex.render,
    "💱 Tasa BCV": tasa_bcv.render,
    "⚙️ Configuración": configuracion.render,
}


def main():
    if not st.session_state.get("autenticado"):
        login()
        return

    # Tasa BCV automática: una vez por sesión, justo después de iniciar sesión
    if "tasa_auto" not in st.session_state:
        with st.spinner("💱 Actualizando la tasa BCV del día..."):
            st.session_state.tasa_auto = tasa_bcv.auto_actualizar_tasa()
        if st.session_state.tasa_auto["estado"] == "ok":
            st.toast(st.session_state.tasa_auto["mensaje"], icon="💱")

    pagina = sidebar.render(MENU, "📊 Dashboard", cerrar_sesion)
    PAGINAS[pagina]()


main()
