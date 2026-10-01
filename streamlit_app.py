import streamlit as st
from app.db import supabase
from app.modules import dashboard, productos, tasa_bcv, ventas

# 1. Configuración de la página (DEBE ser el primer comando de Streamlit)
st.set_page_config(
    page_title="Servicios Autos Led - Sistema de Inventario",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Inicializar session_state ANTES de cualquier uso
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario" not in st.session_state:
    st.session_state.usuario = None


def login():
    st.title("🔐 Iniciar Sesión")
    st.markdown("Sistema Profesional de Inventario y Ventas - Autopartes")

    with st.form("login_form"):
        email = st.text_input("Correo Electrónico")
        password = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Ingresar")

        if submit:
            try:
                res = supabase.auth.sign_in_with_password(
                    {"email": email, "password": password}
                )
                st.session_state.autenticado = True
                st.session_state.usuario = res.user
                st.rerun()
            except Exception as e:
                st.error(f"Error de autenticación: {e}")


def main():
    # .get() evita el KeyError aunque la clave no exista (doble protección)
    if not st.session_state.get("autenticado", False):
        login()
        return

    st.sidebar.title(f"👤 {st.session_state.usuario.email}")
    st.sidebar.markdown("---")

    menu = st.sidebar.radio(
        "Navegación",
        ["Dashboard", "Productos", "Tasa BCV", "Punto de Venta", "Cerrar Sesión"]
    )

    if menu == "Dashboard":
        dashboard.render()
    elif menu == "Productos":
        productos.render()
    elif menu == "Tasa BCV":
        tasa_bcv.render()
    elif menu == "Punto de Venta":
        ventas.render()
    elif menu == "Cerrar Sesión":
        supabase.auth.sign_out()
        st.session_state.autenticado = False
        st.session_state.usuario = None
        st.rerun()


main()
