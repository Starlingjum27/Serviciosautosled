import streamlit as st
from app.db import supabase
import pandas as pd
import unicodedata

def obtener_ultima_tasa():
    """Obtiene la tasa BCV más reciente de la base de datos."""
    try:
        res = supabase.table("tasas_bcv").select("tasa").order("fecha", desc=True).limit(1).execute()
        if res.data:
            return res.data[0]['tasa']
    except:
        pass
    return 0.0

def obtener_categorias():
    """Obtiene la lista de categorías desde la base de datos."""
    try:
        res = supabase.table("categorias").select("nombre").order("nombre").execute()
        if res.data:
            return [c['nombre'] for c in res.data]
    except:
        pass
    # Categorías por defecto si la tabla está vacía
    return ["Luces LED", "Módulos", "Sensores", "Accesorios", "Kits", "Otros"]

def generar_sku(categoria):
    """Genera un SKU automático basado en las 3 primeras letras de la categoría."""
    # Limpiar el nombre de la categoría (quitar acentos, espacios y pasar a mayúsculas)
    texto = unicodedata.normalize('NFKD', categoria).encode('ASCII', 'ignore').decode('utf-8')
    texto = texto.upper().replace(" ", "")
    prefijo = texto[:3] if len(texto) >= 3 else texto.ljust(3, 'X')
    
    try:
        # Contar cuántos productos hay con ese prefijo
        res = supabase.table("productos").select("id").ilike("sku", f"{prefijo}-%").execute()
        count = len(res.data) if res.data else 0
        return f"{prefijo}-{count + 1:04d}"
    except:
        return f"{prefijo}-0001"

def render():
    st.title("📦 Catálogo de Productos")
    tasa_actual = obtener_ultima_tasa()
    
    if "editando_producto" not in st.session_state:
        st.session_state.editando_producto = None

    if tasa_actual == 0.0:
        st.warning("⚠️ No hay tasa BCV registrada. Ve al módulo 'Tasa BCV' y registra una para ver los precios en Bolívares.")
    else:
        st.info(f"💱 Tasa BCV aplicada hoy: **Bs. {tasa_actual:.2f}**")
    
    # --- 1. Gestión de Categorías (NUEVO) ---
    with st.expander("⚙️ Gestionar Categorías", expanded=False):
        st.markdown("¿No encuentras una categoría? Agrégala aquí y estará disponible de inmediato.")
        with st.form("nueva_categoria_form"):
            nueva_cat = st.text_input("Nombre de la Nueva Categoría (Ej: Frenos, Suspensión, Motor)")
            submit_cat = st.form_submit_button("Agregar Categoría")
            if submit_cat and nueva_cat:
                try:
                    supabase.table("categorias").insert({"nombre": nueva_cat}).execute()
                    st.success(f"Categoría '{nueva_cat}' agregada correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al agregar categoría: {e}")

    # --- 2. Formulario para agregar producto ---
    with st.expander("➕ Agregar Nuevo Producto", expanded=False):
        with st.form("nuevo_producto"):
            col1, col2 = st.columns(2)
            with col1:
                # Ahora las categorías se cargan dinámicamente de la base de datos
                categorias_disponibles = obtener_categorias()
                categoria = st.selectbox("Categoría", categorias_disponibles)
                
                sku_auto = generar_sku(categoria)
                st.info(f"🔢 SKU generado automáticamente: **{sku_auto}**")
                nombre = st.text_input("Nombre del Producto")
                marca = st.text_input("Marca")
                stock_actual = st.number_input("Stock Inicial", min_value=0, step=1)
            with col2:
                precio_usd = st.number_input("Precio Venta (USD)", min_value=0.0, step=0.01)
                costo_usd = st.number_input("Costo (USD)", min_value=0.0, step=0.01)
                stock_minimo = st.number_input("Stock Mínimo", min_value=0, step=1, value=5)
            
            submit = st.form_submit_button("Guardar Producto")
            
            if submit:
                if not nombre:
                    st.error("El nombre del producto es obligatorio.")
                else:
                    try:
                        data = {
                            "sku": sku_auto, "nombre": nombre, "marca": marca,
                            "precio_usd": precio_usd, "costo_usd": costo_usd,
                            "stock_actual": stock_actual, "stock_minimo": stock_minimo
                        }
                        supabase.table("productos").insert(data).execute()
                        st.success(f"Producto '{nombre}' agregado con SKU {sku_auto}.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    # --- 3. Buscador y Listado ---
    st.subheader("🔍 Buscar y Listar Productos")
    busqueda = st.text_input("Buscar por SKU, Nombre o Marca", "")
    
    try:
        res = supabase.table("productos").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            
            if busqueda:
                mask = df[['sku', 'nombre', 'marca']].astype(str).apply(
                    lambda x: x.str.contains(busqueda, case=False, na=False)
                ).any(axis=1)
                df = df[mask]
            
            if not df.empty:
                df['precio_bs'] = df['precio_usd'] * tasa_actual if tasa_actual else 0.0
                df['precio_bs'] = df['precio_bs'].apply(lambda x: f"Bs. {x:.2f}" if tasa_actual else "N/A")
                df['precio_usd'] = df['precio_usd'].apply(lambda x: f"${x:.2f}")
                df['costo_usd'] = df['costo_usd'].apply(lambda x: f"${x:.2f}")
                
                columnas_mostrar = ['sku', 'nombre', 'marca', 'stock_actual', 'precio_usd', 'precio_bs']
                st.dataframe(df[columnas_mostrar], use_container_width=True, hide_index=True)
            else:
                st.warning("No se encontraron productos con ese criterio.")
        else:
            st.warning("No hay productos registrados.")
    except Exception as e:
        st.error(f"Error cargando productos: {e}")

    # --- 4. Editar / Eliminar ---
    st.markdown("---")
    st.subheader("🛠️ Gestionar Producto (Editar / Eliminar)")
    
    try:
        res = supabase.table("productos").select("id, sku, nombre").execute()
        if res.data:
            opciones = {f"{p['sku']} - {p['nombre']}": p['id'] for p in res.data}
            producto_seleccionado = st.selectbox("Seleccione un producto para gestionar", ["Seleccione..."] + list(opciones.keys()))
            
            if producto_seleccionado != "Seleccione...":
                id_producto = opciones[producto_seleccionado]
                
                col_edit, col_del = st.columns(2)
                
                with col_edit:
                    if st.button("✏️ Editar Producto"):
                        st.session_state.editando_producto = id_producto
                
                with col_del:
                    if st.button("🗑️ Eliminar Producto"):
                        supabase.table("productos").delete().eq("id", id_producto).execute()
                        st.success(f"Producto eliminado.")
                        st.rerun()

                if st.session_state.editando_producto == id_producto:
                    datos = supabase.table("productos").select("*").eq("id", id_producto).execute().data[0]
                    with st.form("editar_producto_form"):
                        st.write(f"Editando: **{datos['sku']} - {datos['nombre']}**")
                        col1, col2 = st.columns(2)
                        with col1:
                            nuevo_nombre = st.text_input("Nombre", value=datos['nombre'])
                            nuevo_marca = st.text_input("Marca", value=datos.get('marca', ''))
                            nuevo_stock = st.number_input("Stock Actual", value=int(datos.get('stock_actual', 0)))
                        with col2:
                            nuevo_precio = st.number_input("Precio USD", value=float(datos['precio_usd']))
                            nuevo_costo = st.number_input("Costo USD", value=float(datos['costo_usd']))
                            nuevo_minimo = st.number_input("Stock Mínimo", value=int(datos.get('stock_minimo', 5)))
                        
                        col_guardar, col_cancelar = st.columns(2)
                        with col_guardar:
                            if st.form_submit_button("💾 Guardar Cambios"):
                                supabase.table("productos").update({
                                    "nombre": nuevo_nombre, "marca": nuevo_marca,
                                    "precio_usd": nuevo_precio, "costo_usd": nuevo_costo,
                                    "stock_actual": nuevo_stock, "stock_minimo": nuevo_minimo
                                }).eq("id", id_producto).execute()
                                st.success("Producto actualizado exitosamente.")
                                st.session_state.editando_producto = None
                                st.rerun()
                        with col_cancelar:
                            if st.form_submit_button("❌ Cancelar"):
                                st.session_state.editando_producto = None
                                st.rerun()
    except Exception as e:
        st.error(f"Error en gestión de productos: {e}")
