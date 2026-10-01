"""
Conexión a Supabase.

IMPORTANTE: antes había UN solo cliente global para toda la app. En Streamlit
Cloud todos los usuarios comparten el mismo proceso, así que el login de una
persona se "compartía" con los demás y un "Cerrar sesión" sacaba a todos.
Ahora cada sesión del navegador tiene su propio cliente (y su propio token),
lo que además permite activar RLS en la base de datos.

Los módulos siguen usando:  from app.db import supabase
"""
import streamlit as st
from supabase import create_client, Client

_CLAVE = "_supabase_client"


def _crear_cliente() -> Client:
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except Exception as e:
        st.error(f"Error conectando a Supabase: {e}")
        st.stop()


def get_client() -> Client:
    if _CLAVE not in st.session_state:
        st.session_state[_CLAVE] = _crear_cliente()
    return st.session_state[_CLAVE]


def reset_client() -> None:
    """Descarta el cliente de esta sesión (usar al cerrar sesión)."""
    st.session_state.pop(_CLAVE, None)


class _ClientePorSesion:
    """Proxy: reenvía todo al cliente de la sesión actual."""

    def __getattr__(self, nombre):
        return getattr(get_client(), nombre)


supabase = _ClientePorSesion()
