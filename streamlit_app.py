import streamlit as st

# 1. Configuración de la página (DEBE ser el primer comando de Streamlit)
st.set_page_config(
    page_title="Servicios Autos Led - Sistema de Inventario",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

from app.db import supabase, reset_client  # noqa: E402
from app.modules import dashboard, productos, tasa_bcv, ventas, configuracion  # noqa: E402

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


PAGINAS = {
    "📊 Dashboard": dashboard.render,
    "🛒 Punto de Venta": ventas.render,
    "📦 Productos": productos.render,
    "💱 Tasa BCV": tasa_bcv.render,
    "⚙️ Configuración": configuracion.render,
}


def main():
    if not st.session_state.get("autenticado"):
        login()
        return

    st.sidebar.markdown(f"👤 **{st.session_state.usuario.email}**")
    st.sidebar.divider()
    pagina = st.sidebar.radio("Navegación", list(PAGINAS), key="nav")
    st.sidebar.divider()
    if st.sidebar.button("🚪 Cerrar sesión", use_container_width=True):
        cerrar_sesion()
    PAGINAS[pagina]()


main()
