import streamlit as st
from supabase import create_client, Client

def init_supabase() -> Client:
    """Inicializa y retorna el cliente de Supabase."""
    try:
        # En local usa st.secrets, en producción también funciona
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Error conectando a Supabase: {e}")
        st.stop()

# Instancia global para usar en los módulos
supabase = init_supabase()
