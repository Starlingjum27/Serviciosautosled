import streamlit as st
from app.db import supabase
import datetime

def render():
    st.title("💱 Módulo Tasa BCV")
    st.markdown("Registro y consulta de la tasa oficial del Banco Central de Venezuela.")
    
    st.subheader("Registrar Tasa del Día")
    with st.form("tasa_form"):
        fecha = st.date_input("Fecha", datetime.date.today())
        tasa = st.number_input("Tasa BCV (Bs/USD)", min_value=0.0, format="%.4f")
        submit = st.form_submit_button("Guardar Tasa")
        
        if submit:
            try:
                data = {"fecha": str(fecha), "tasa": tasa, "fuente": "Manual"}
                supabase.table("tasas_bcv").insert(data).execute()
                st.success("Tasa registrada correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

    st.subheader("Histórico de Tasas")
    try:
        res = supabase.table("tasas_bcv").select("*").order("fecha", desc=True).limit(10).execute()
        if res.data:
            st.dataframe(res.data, use_container_width=True)
        else:
            st.info("No hay tasas registradas.")
    except Exception as e:
        st.error(f"Error cargando tasas: {e}")
