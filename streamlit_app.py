import streamlit as st
from app.db import supabase
from app.modules import dashboard, productos, tasa_bcv


# ... (resto del código de configuración y login igual) ...

def main():
    if not st.session_state.autenticado:
        login()
    else:
        st.sidebar.title(f"👤 {st.session_state.usuario.email}")
        st.sidebar.markdown("---")
        
        menu = st.sidebar.radio(
            "Navegación",
            ["Dashboard", "Productos", "Tasa BCV", "Punto de Venta", "Cerrar Sesión"] # <-- Agregamos la opción
        )
        
        if menu == "Dashboard":
            dashboard.render()
        elif menu == "Productos":
            productos.render()
        elif menu == "Tasa BCV":
            tasa_bcv.render()
        elif menu == "Punto de Venta": # <-- Agregamos la lógica
            ventas.render()
        elif menu == "Cerrar Sesión":
            supabase.auth.sign_out()
            st.session_state.autenticado = False
            st.session_state.usuario = None
            st.rerun()

if __name__ == "__main__":
    main()

# Configuración de la página
st.set_page_config(
    page_title="Servicios Autos Led - Sistema de Inventario",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializar estado de sesión para autenticación
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
                # Autenticación con Supabase Auth
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.autenticado = True
                st.session_state.usuario = res.user
                st.success("¡Bienvenido!")
                st.rerun()
            except Exception as e:
                st.error(f"Error de autenticación: {e}")

def main():
    if not st.session_state.autenticado:
        login()
    else:
        # Menú lateral
        st.sidebar.title(f"👤 {st.session_state.usuario.email}")
        st.sidebar.markdown("---")
        
        menu = st.sidebar.radio(
            "Navegación",
            ["Dashboard", "Productos", "Tasa BCV", "Cerrar Sesión"]
        )
        
        if menu == "Dashboard":
            dashboard.render()
        elif menu == "Productos":
            productos.render()
        elif menu == "Tasa BCV":
            tasa_bcv.render()
        elif menu == "Cerrar Sesión":
            supabase.auth.sign_out()
            st.session_state.autenticado = False
            st.session_state.usuario = None
            st.rerun()

if __name__ == "__main__":
    main()
