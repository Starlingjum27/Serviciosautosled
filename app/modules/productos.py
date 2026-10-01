import streamlit as st
from app.db import supabase

def obtener_ultima_tasa():
    """Obtiene la tasa BCV más reciente de la base de datos."""
    try:
        res = supabase.table("tasas_bcv").select("tasa").order("fecha", desc=True).limit(1).execute()
        if res.data:
            return res.data[0]['tasa']
    except:
        pass
    return 0.0

def render():
    st.title("📦 Catálogo de Productos")
    
    tasa_actual = obtener_ultima_tasa()
    
    if tasa_actual == 0.0:
        st.warning("⚠️ No hay tasa BCV registrada. Ve al módulo 'Tasa BCV' y registra una para ver los precios en Bolívares.")
    else:
        st.info(f"💱 Tasa BCV aplicada hoy: **Bs. {tasa_actual:.2f}**")
    
    # Formulario para agregar producto
    with st.expander("➕ Agregar Nuevo Producto"):
        with st.form("nuevo_producto"):
            col1, col2 = st.columns(2)
            with col1:
                sku = st.text_input("SKU")
                nombre = st.text_input("Nombre del Producto")
                marca = st.text_input("Marca")
                categoria = st.selectbox("Categoría", ["Luces LED", "Módulos", "Sensores", "Accesorios", "Kits", "Otros"])
                stock_actual = st.number_input("Stock Inicial", min_value=0, step=1)
            with col2:
                precio_usd = st.number_input("Precio Venta (USD)", min_value=0.0, step=0.01)
                costo_usd = st.number_input("Costo (USD)", min_value=0.0, step=0.01)
                stock_minimo = st.number_input("Stock Mínimo", min_value=0, step=1, value=5)
            
            submit = st.form_submit_button("Guardar Producto")
            
            if submit:
                try:
                    data = {
                        "sku": sku, "nombre": nombre, "marca": marca,
                        "precio_usd": precio_usd, "costo_usd": costo_usd,
                        "stock_actual": stock_actual, "stock_minimo": stock_minimo
                    }
                    supabase.table("productos").insert(data).execute()
                    st.success("Producto agregado exitosamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    # Listar productos
    st.subheader("Lista de Productos")
    try:
        res = supabase.table("productos").select("*").execute()
        if res.data:
            # Preparar datos para mostrar en tabla
            productos_mostrar = []
            for p in res.data:
                precio_bs = p['precio_usd'] * tasa_actual if tasa_actual else 0.0
                productos_mostrar.append({
                    "SKU": p['sku'],
                    "Nombre": p['nombre'],
                    "Marca": p.get('marca', ''),
                    "Stock": p.get('stock_actual', 0),
                    "Precio USD": f"${p['precio_usd']:.2f}",
                    "Precio Bs": f"Bs. {precio_bs:.2f}" if tasa_actual else "N/A",
                    "Costo USD": f"${p['costo_usd']:.2f}",
                })
            st.dataframe(productos_mostrar, use_container_width=True)
        else:
            st.warning("No hay productos registrados.")
    except Exception as e:
        st.error(f"Error cargando productos: {e}")
