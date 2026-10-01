import streamlit as st
from app.db import supabase

def render():
    st.title("📦 Catálogo de Productos")
    
    with st.expander("➕ Agregar Nuevo Producto"):
        with st.form("nuevo_producto"):
            sku = st.text_input("SKU")
            nombre = st.text_input("Nombre del Producto")
            precio_usd = st.number_input("Precio Venta (USD)", min_value=0.0, step=0.01)
            costo_usd = st.number_input("Costo (USD)", min_value=0.0, step=0.01)
            submit = st.form_submit_button("Guardar Producto")
            
            if submit:
                try:
                    data = {
                        "sku": sku, "nombre": nombre, 
                        "precio_usd": precio_usd, "costo_usd": costo_usd
                    }
                    supabase.table("productos").insert(data).execute()
                    st.success("Producto agregado exitosamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    st.subheader("Lista de Productos")
    try:
        res = supabase.table("productos").select("*").execute()
        if res.data:
            st.dataframe(res.data, use_container_width=True)
        else:
            st.warning("No hay productos registrados.")
    except Exception as e:
        st.error(f"Error cargando productos: {e}")
