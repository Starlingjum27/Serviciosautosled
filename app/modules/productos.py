import streamlit as st
from app.db import supabase
import pandas as pd
import unicodedata

# --- FUNCIONES AUXILIARES ---
def obtener_ultima_tasa():
    try:
        res = supabase.table("tasas_bcv").select("tasa").order("fecha", desc=True).limit(1).execute()
        if res.data:
            return res.data[0]['tasa']
    except:
        pass
    return 0.0

def obtener_categorias():
    try:
        res = supabase.table("categorias").select("id, nombre").order("nombre").execute()
        return res.data if res.data else []
    except:
        return []

def generar_sku(nombre_categoria):
    texto = unicodedata.normalize('NFKD', nombre_categoria).encode('ASCII', 'ignore').decode('utf-8')
    texto = texto.upper().replace(" ", "")
    prefijo = texto[:3] if len(texto) >= 3 else texto.ljust(3, 'X')
    try:
        res = supabase.table("productos").select("id").ilike("sku", f"{prefijo}-%").execute()
        count = len(res.data) if res.data else 0
        return f"{prefijo}-{count + 1:04d}"
    except:
        return f"{prefijo}-0001"

# --- MÓDULO PRINCIPAL ---
def render():
    st.title("📦 Gestión de Inventario")
    tasa_actual = obtener_ultima_tasa()
    
    if tasa_actual == 0.0:
        st.warning("⚠️ No hay tasa BCV registrada. Ve al módulo 'Tasa BCV' y registra una.")
    else:
        st.info(f"💱 Tasa BCV aplicada hoy: **Bs. {tasa_actual:.2f}**")

    # Crear pestañas para organizar la pantalla
    tab_catalogo, tab_categorias = st.tabs(["📋 Catálogo de Productos", "⚙️ Gestión de Categorías"])

    # ==========================================
    # PESTAÑA 1: CATÁLOGO DE PRODUCTOS
    # ==========================================
    with tab_catalogo:
        # --- Formulario Nuevo Producto ---
        with st.expander("➕ Agregar Nuevo Producto", expanded=False):
            categorias = obtener_categorias()
            if not categorias:
                st.warning("Primero debes crear al menos una categoría en la pestaña 'Gestión de Categorías'.")
            else:
                with st.form("nuevo_producto_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        cat_seleccionada = st.selectbox("Categoría", categorias, format_func=lambda x: x['nombre'])
                        sku_auto = generar_sku(cat_seleccionada['nombre'])
                        st.info(f"🔢 SKU generado: **{sku_auto}**")
                        nombre = st.text_input("Nombre del Producto")
                        marca = st.text_input("Marca")
                        stock_actual = st.number_input("Stock Inicial", min_value=0, step=1)
                    with col2:
                        precio_usd = st.number_input("Precio Venta (USD)", min_value=0.0, step=0.01)
                        costo_usd = st.number_input("Costo (USD)", min_value=0.0, step=0.01)
                        stock_minimo = st.number_input("Stock Mínimo (Alerta)", min_value=0, step=1, value=5)
                    
                    if st.form_submit_button("💾 Guardar Producto"):
                        if not nombre:
                            st.error("El nombre es obligatorio.")
                        else:
                            try:
                                data = {
                                    "sku": sku_auto, "nombre": nombre, "marca": marca,
                                    "categoria_id": cat_seleccionada['id'],
                                    "precio_usd": precio_usd, "costo_usd": costo_usd,
                                    "stock_actual": stock_actual, "stock_minimo": stock_minimo
                                }
                                supabase.table("productos").insert(data).execute()
                                st.success(f"Producto '{nombre}' guardado con SKU {sku_auto}.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

        # --- Listado y Búsqueda ---
        st.subheader("🔍 Inventario Actual")
        
        col_busq, col_filtro = st.columns([2, 1])
        with col_busq:
            busqueda = st.text_input("Buscar por SKU, Nombre o Marca", "")
        with col_filtro:
            filtro_cat = st.selectbox("Filtrar por Categoría", ["Todas"] + [c['nombre'] for c in obtener_categorias()])

        try:
            # Hacemos un "join" manual para traer el nombre de la categoría
            res_prod = supabase.table("productos").select("*").execute()
            res_cat = supabase.table("categorias").select("id, nombre").execute()
            
            if res_prod.data:
                df = pd.DataFrame(res_prod.data)
                df_cat = pd.DataFrame(res_cat.data)
                
                # Mapear categoria_id a nombre
                if not df_cat.empty:
                    df = df.merge(df_cat, left_on='categoria_id', right_on='id', how='left', suffixes=('', '_cat'))
                    df['categoria_nombre'] = df['nombre_cat'].fillna('Sin Categoría')
                else:
                    df['categoria_nombre'] = 'Sin Categoría'

                # Aplicar Filtros
                if busqueda:
                    mask = df[['sku', 'nombre', 'marca']].astype(str).apply(
                        lambda x: x.str.contains(busqueda, case=False, na=False)
                    ).any(axis=1)
                    df = df[mask]
                
                if filtro_cat != "Todas":
                    df = df[df['categoria_nombre'] == filtro_cat]

                if not df.empty:
                    # Formatear precios y alertas de stock
                    df['precio_bs'] = df['precio_usd'] * tasa_actual if tasa_actual else 0.0
                    df['precio_bs'] = df['precio_bs'].apply(lambda x: f"Bs. {x:.2f}" if tasa_actual else "N/A")
                    df['precio_usd_fmt'] = df['precio_usd'].apply(lambda x: f"${x:.2f}")
                    
                    def alerta_stock(row):
                        if row['stock_actual'] == 0: return "❌ AGOTADO"
                        if row['stock_actual'] <= row['stock_minimo']: return "⚠️ BAJO"
                        return "✅ OK"
                    
                    df['Alerta'] = df.apply(alerta_stock, axis=1)
                    
                    columnas = ['sku', 'nombre', 'marca', 'categoria_nombre', 'stock_actual', 'Alerta', 'precio_usd_fmt', 'precio_bs']
                    st.dataframe(df[columnas], use_container_width=True, hide_index=True)
                else:
                    st.info("No se encontraron productos.")
            else:
                st.info("No hay productos registrados aún.")
        except Exception as e:
            st.error(f"Error cargando inventario: {e}")

        # --- Editar / Eliminar Producto ---
        st.markdown("---")
        st.subheader("🛠️ Editar o Eliminar Producto")
        try:
            res = supabase.table("productos").select("id, sku, nombre").execute()
            if res.data:
                opciones = {f"{p['sku']} - {p['nombre']}": p['id'] for p in res.data}
                prod_sel = st.selectbox("Seleccione un producto", ["Seleccione..."] + list(opciones.keys()))
                
                if prod_sel != "Seleccione...":
                    id_prod = opciones[prod_sel]
                    col_edit, col_del = st.columns(2)
                    
                    with col_edit:
                        if st.button("✏️ Editar"):
                            st.session_state.editando_producto = id_prod
                    with col_del:
                        if st.button("🗑️ Eliminar"):
                            supabase.table("productos").delete().eq("id", id_prod).execute()
                            st.success("Producto eliminado.")
                            st.rerun()

                    if st.session_state.get('editando_producto') == id_prod:
                        datos = supabase.table("productos").select("*").eq("id", id_prod).execute().data[0]
                        cats = obtener_categorias()
                        idx_cat = next((i for i, c in enumerate(cats) if c['id'] == datos.get('categoria_id')), 0)
                        
                        with st.form("editar_prod_form"):
                            st.write(f"Editando: **{datos['sku']}**")
                            c1, c2 = st.columns(2)
                            with c1:
                                n_nombre = st.text_input("Nombre", value=datos['nombre'])
                                n_marca = st.text_input("Marca", value=datos.get('marca', ''))
                                n_cat = st.selectbox("Categoría", cats, index=idx_cat, format_func=lambda x: x['nombre'])
                                n_stock = st.number_input("Stock Actual", value=int(datos.get('stock_actual', 0)))
                            with c2:
                                n_precio = st.number_input("Precio USD", value=float(datos['precio_usd']))
                                n_costo = st.number_input("Costo USD", value=float(datos['costo_usd']))
                                n_minimo = st.number_input("Stock Mínimo", value=int(datos.get('stock_minimo', 5)))
                            
                            if st.form_submit_button("💾 Guardar Cambios"):
                                supabase.table("productos").update({
                                    "nombre": n_nombre, "marca": n_marca, "categoria_id": n_cat['id'],
                                    "precio_usd": n_precio, "costo_usd": n_costo,
                                    "stock_actual": n_stock, "stock_minimo": n_minimo
                                }).eq("id", id_prod).execute()
                                st.session_state.editando_producto = None
                                st.success("Producto actualizado.")
                                st.rerun()
        except Exception as e:
            st.error(f"Error en gestión: {e}")

    # ==========================================
    # PESTAÑA 2: GESTIÓN DE CATEGORÍAS
    # ==========================================
    with tab_categorias:
        st.subheader("Crear Nueva Categoría")
        with st.form("nueva_cat_form"):
            nueva_cat = st.text_input("Nombre de la Categoría (Ej: Frenos, Suspensión)")
            if st.form_submit_button("➕ Agregar Categoría"):
                if nueva_cat:
                    try:
                        supabase.table("categorias").insert({"nombre": nueva_cat}).execute()
                        st.success(f"Categoría '{nueva_cat}' creada.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.warning("Escribe un nombre.")

        st.markdown("---")
        st.subheader("Categorías Existentes")
        
        categorias = obtener_categorias()
        if categorias:
            for cat in categorias:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(f"📁 **{cat['nombre']}**")
                with col2:
                    if st.button("✏️ Editar", key=f"edit_cat_{cat['id']}"):
                        st.session_state.editando_categoria = cat['id']
                with col3:
                    if st.button("🗑️ Eliminar", key=f"del_cat_{cat['id']}"):
                        # Verificar si tiene productos asociados
                        prod_asociados = supabase.table("productos").select("id").eq("categoria_id", cat['id']).execute()
                        if prod_asociados.data:
                            st.error(f"No se puede eliminar '{cat['nombre']}' porque tiene productos asociados.")
                        else:
                            supabase.table("categorias").delete().eq("id", cat['id']).execute()
                            st.success(f"Categoría '{cat['nombre']}' eliminada.")
                            st.rerun()

                # Formulario de edición de categoría
                if st.session_state.get('editando_categoria') == cat['id']:
                    with st.form(f"edit_cat_form_{cat['id']}"):
                        nuevo_nombre = st.text_input("Nuevo Nombre", value=cat['nombre'])
                        if st.form_submit_button("💾 Guardar"):
                            supabase.table("categorias").update({"nombre": nuevo_nombre}).eq("id", cat['id']).execute()
                            st.session_state.editando_categoria = None
                            st.success("Categoría actualizada.")
                            st.rerun()
        else:
            st.info("No hay categorías registradas.")
