import streamlit as st
from app.db import supabase

def render():
    st.title("📊 Dashboard Principal")
    st.markdown("Resumen general del sistema.")
    
    col1, col2, col3 = st.columns(3)
    
    try:
        productos_res = supabase.table("productos").select("id", count="exact").execute()
        total_productos = productos_res.count if productos_res.count else 0
    except:
        total_productos = 0

    col1.metric("Total Productos", total_productos)
    col2.metric("Ventas Hoy (USD)", "$0.00")
    col3.metric("Tasa BCV Hoy", "Bs. 0.00")
    
    st.info("Módulo en construcción. Fase 1 completada.")
