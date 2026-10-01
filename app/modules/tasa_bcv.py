import streamlit as st
from app.db import supabase
import datetime
import requests

def obtener_tasa_automatica():
    """Intenta obtener la tasa del BCV desde una API pública."""
    try:
        # Usamos una API pública que refleja la tasa oficial del BCV
        url = "https://ve.dolarapi.com/v1/dolares/oficial"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return float(data.get("promedio", 0.0))
    except Exception as e:
        return None
    return None

def render():
    st.title("💱 Módulo Tasa BCV")
    st.markdown("Registro y consulta de la tasa oficial del Banco Central de Venezuela.")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Actualización Automática")
        if st.button("🔄 Obtener Tasa BCV de Hoy"):
            with st.spinner("Buscando tasa en el BCV..."):
                tasa_auto = obtener_tasa_automatica()
                if tasa_auto:
                    st.session_state['tasa_sugerida'] = tasa_auto
                    st.success(f"Tasa encontrada: Bs. {tasa_auto:.2f}")
                else:
                    st.error("No se pudo conectar. Ingresa la tasa manualmente abajo.")

    with col2:
        st.subheader("Registro Manual / Confirmación")
        with st.form("tasa_form"):
            fecha = st.date_input("Fecha", datetime.date.today())
            # Si hay una tasa sugerida por el sistema, la ponemos por defecto
            tasa_default = st.session_state.get('tasa_sugerida', 0.0)
            tasa = st.number_input("Tasa BCV (Bs/USD)", min_value=0.0, value=tasa_default, format="%.4f")
            submit = st.form_submit_button("Guardar Tasa")
            
            if submit:
                try:
                    data = {"fecha": str(fecha), "tasa": tasa, "fuente": "Automática/Manual"}
                    # Verificar si ya existe la tasa para esa fecha
                    existing = supabase.table("tasas_bcv").select("id").eq("fecha", str(fecha)).execute()
                    if existing.data:
                        supabase.table("tasas_bcv").update(data).eq("fecha", str(fecha)).execute()
                        st.success("Tasa actualizada correctamente.")
                    else:
                        supabase.table("tasas_bcv").insert(data).execute()
                        st.success("Tasa registrada correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

    st.markdown("---")
    st.subheader("Histórico de Tasas")
    try:
        res = supabase.table("tasas_bcv").select("*").order("fecha", desc=True).limit(10).execute()
        if res.data:
            st.dataframe(res.data, use_container_width=True)
        else:
            st.info("No hay tasas registradas.")
    except Exception as e:
        st.error(f"Error cargando tasas: {e}")
