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

# ============================================
# VENTANAS MODALES (POP-UPS)
# ============================================

@st.dialog("➕ Agregar Nuevo Producto")
def dialog_nuevo_producto():
    categorias = obtener_categorias()
    if not categorias:
        st.warning("Primero crea una categoría.")
        if st.button("Cerrar", use_container_width=True):
            st.rerun()
        return
    
    cat_sel = st.selectbox("Categoría", categorias, format_func=lambda x: x['nombre'])
    sku_auto = generar_sku(cat_sel['nombre'])
    st.info(f"🔢 SKU generado: **{sku_auto}**")
    
    nombre = st.text_input("Nombre del Producto *")
    marca = st.text_input("Marca")
    
    col1, col2 = st.columns(2)
    with col1:
        precio_usd = st.number_input("Precio Venta (USD) *", min_value=0.0, step=0.01)
        costo_usd = st.number_input("Costo (USD)", min_value=0.0, step=0.01)
    with col2:
        stock_actual = st.number_input("Stock Inicial", min_value=0, step=1)
        stock_minimo = st.number_input("Stock Mínimo", min_value=0, step=1, value=5)
    
    st.markdown("---")
    col_g, col_c = st.columns(2)
    with col_g:
        if st.button("💾 Guardar Producto", use_container_width=True, type="primary"):
            if not nombre or precio_usd <= 0:
                st.error("Nombre y precio son obligatorios.")
            else:
                try:
                    data = {
                        "sku": sku_auto, "nombre": nombre, "marca": marca,
                        "categoria_id": cat_sel['id'],
                        "precio_usd": precio_usd, "costo_usd": costo_usd,
                        "stock_actual": stock_actual, "stock_minimo": stock_minimo
                    }
                    supabase.table("productos").insert(data).execute()
                    st.success(f"Producto '{nombre}' guardado.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
    with col_c:
        if st.button("❌ Cancelar", use_container_width=True):
            st.rerun()

@st.dialog("✏️ Editar Producto")
def dialog_editar_producto(id_prod):
    try:
        datos = supabase.table("productos").select("*").eq("id", id_prod).execute().data[0]
    except:
        st.error("No se pudo cargar.")
        if st.button("Cerrar"):
            st.rerun()
        return
    
    st.markdown(f"**SKU:** `{datos['sku']}`")
    cats = obtener_categorias()
    idx_cat = next((i for i, c in enumerate(cats) if c['id'] == datos.get('categoria_id')), 0)
    
    n_cat = st.selectbox("Categoría", cats, index=idx_cat, format_func=lambda x: x['nombre'])
    n_nombre = st.text_input("Nombre", value=datos['nombre'])
    n_marca = st.text_input("Marca", value=datos.get('marca', '') or '')
    
    col1, col2 = st.columns(2)
    with col1:
        n_precio = st.number_input("Precio USD", value=float(datos['precio_usd']), min_value=0.0, step=0.01)
        n_costo = st.number_input("Costo USD", value=float(datos['costo_usd']), min_value=0.0, step=0.01)
    with col2:
        n_stock = st.number_input("Stock Actual", value=int(datos.get('stock_actual', 0)), min_value=0, step=1)
        n_minimo = st.number_input("Stock Mínimo", value=int(datos.get('stock_minimo', 5)), min_value=0, step=1)
    
    st.markdown("---")
    col_g, col_c = st.columns(2)
    with col_g:
        if st.button("💾 Guardar Cambios", use_container_width=True, type="primary"):
            if not n_nombre:
                st.error("Nombre obligatorio.")
            else:
                try:
                    supabase.table("productos").update({
                        "nombre": n_nombre, "marca": n_marca, "categoria_id": n_cat['id'],
                        "precio_usd": n_precio, "costo_usd": n_costo,
                        "stock_actual": n_stock, "stock_minimo": n_minimo
                    }).eq("id", id_prod).execute()
                    st.success("Actualizado correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
    with col_c:
        if st.button("❌ Cancelar", use_container_width=True):
            st.rerun()

@st.dialog("🗑️ Confirmar Eliminación")
def dialog_eliminar_producto(id_prod, sku, nombre):
    st.warning("¿Estás seguro de eliminar este producto?")
    st.markdown(f"**{sku}** - {nombre}")
    st.markdown("⚠️ *Esta acción no se puede deshacer.*")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Sí, Eliminar", use_container_width=True, type="primary"):
            try:
                supabase.table("productos").delete().eq("id", id_prod).execute()
                st.success("Producto eliminado.")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
    with col2:
        if st.button("❌ Cancelar", use_container_width=True):
            st.rerun()

@st.dialog("✏️ Editar Categoría")
def dialog_editar_categoria(id_cat, nombre_actual):
    nuevo_nombre = st.text_input("Nuevo Nombre", value=nombre_actual)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Guardar", use_container_width=True, type="primary"):
            if nuevo_nombre:
                try:
                    supabase.table("categorias").update({"nombre": nuevo_nombre}).eq("id", id_cat).execute()
                    st.success("Categoría actualizada.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
    with col2:
        if st.button("❌ Cancelar", use_container_width=True):
            st.rerun()

@st.dialog("🗑️ Eliminar Categoría")
def dialog_eliminar_categoria(id_cat, nombre):
    prod_asociados = supabase.table("productos").select("id").eq("categoria_id", id_cat).execute()
    if prod_asociados.data:
        st.error(f"No se puede eliminar **'{nombre}'** porque tiene {len(prod_asociados.data)} productos asociados.")
        if st.button("Cerrar", use_container_width=True):
            st.rerun()
        return
    
    st.warning(f"¿Eliminar la categoría **{nombre}**?")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Sí, Eliminar", use_container_width=True, type="primary"):
            supabase.table("categorias").delete().eq("id", id_cat).execute()
            st.success("Categoría eliminada.")
            st.rerun()
    with col2:
        if st.button("❌ Cancelar", use_container_width=True):
            st.rerun()

# ============================================
# MÓDULO PRINCIPAL
# ============================================
def render():
    st.title("📦 Gestión de Inventario")
    tasa_actual = obtener_ultima_tasa()
    
    if tasa_actual == 0.0:
        st.warning("⚠️ No hay tasa BCV registrada.")
    else:
        st.info(f"💱 Tasa BCV aplicada hoy: **Bs. {tasa_actual:.2f}**")

    tab_catalogo, tab_categorias, tab_importar = st.tabs([
        "📋 Catálogo de Productos", "⚙️ Gestión de Categorías", "📥 Carga Masiva (Excel)"
    ])

    # --- TAB CATÁLOGO ---
    with tab_catalogo:
        if st.button("➕ Agregar Nuevo Producto", type="primary"):
            dialog_nuevo_producto()

        st.markdown("### 🔍 Inventario Actual")
        col_busq, col_filtro = st.columns([2, 1])
        with col_busq:
            busqueda = st.text_input("Buscar por SKU, Nombre o Marca", "")
        with col_filtro:
            filtro_cat = st.selectbox("Filtrar por Categoría", ["Todas"] + [c['nombre'] for c in obtener_categorias()])

        try:
            res_prod = supabase.table("productos").select("*").execute()
            res_cat = supabase.table("categorias").select("id, nombre").execute()
            
            if res_prod.data:
                df = pd.DataFrame(res_prod.data)
                if 'categoria_id' in df.columns:
                    df['categoria_id'] = pd.to_numeric(df['categoria_id'], errors='coerce').fillna(0).astype(int)
                else:
                    df['categoria_id'] = 0
                
                if res_cat.data:
                    df_cat = pd.DataFrame(res_cat.data)
                    df_cat['id'] = pd.to_numeric(df_cat['id'], errors='coerce').fillna(0).astype(int)
                    df = df.merge(df_cat, left_on='categoria_id', right_on='id', how='left', suffixes=('', '_cat'))
                    df['categoria_nombre'] = df['nombre_cat'].fillna('Sin Categoría')
                else:
                    df['categoria_nombre'] = 'Sin Categoría'

                if busqueda:
                    mask = df[['sku', 'nombre', 'marca']].astype(str).apply(
                        lambda x: x.str.contains(busqueda, case=False, na=False)
                    ).any(axis=1)
                    df = df[mask]
                
                if filtro_cat != "Todas":
                    df = df[df['categoria_nombre'] == filtro_cat]

                if not df.empty:
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

        # --- Acciones Rápidas (Botones por producto) ---
        st.markdown("---")
        st.markdown("### 🛠️ Editar / Eliminar Productos")
        
        try:
            res = supabase.table("productos").select("id, sku, nombre").order("nombre").execute()
            if res.data:
                busqueda_accion = st.text_input("Buscar producto para gestionar", key="busqueda_accion")
                productos_filtrados = res.data
                if busqueda_accion:
                    productos_filtrados = [p for p in res.data if busqueda_accion.lower() in f"{p['sku']} {p['nombre']}".lower()]
                
                if productos_filtrados:
                    for p in productos_filtrados[:30]:
                        col_info, col_edit, col_del = st.columns([6, 1, 1])
                        with col_info:
                            st.write(f"`{p['sku']}` — {p['nombre']}")
                        with col_edit:
                            if st.button("✏️", key=f"btn_edit_{p['id']}", help="Editar"):
                                dialog_editar_producto(p['id'])
                        with col_del:
                            if st.button("🗑️", key=f"btn_del_{p['id']}", help="Eliminar"):
                                dialog_eliminar_producto(p['id'], p['sku'], p['nombre'])
                else:
                    st.info("No se encontraron productos.")
        except Exception as e:
            st.error(f"Error: {e}")

    # --- TAB CATEGORÍAS ---
    with tab_categorias:
        st.subheader("➕ Crear Nueva Categoría")
        with st.form("nueva_cat_form", clear_on_submit=True):
            col_input, col_btn = st.columns([3, 1])
            with col_input:
                nueva_cat = st.text_input("Nombre", label_visibility="collapsed", placeholder="Ej: Frenos, Suspensión, Motor...")
            with col_btn:
                submit_cat = st.form_submit_button("➕ Agregar", use_container_width=True)
            
            if submit_cat and nueva_cat:
                try:
                    supabase.table("categorias").insert({"nombre": nueva_cat}).execute()
                    st.success(f"Categoría '{nueva_cat}' creada.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

        st.markdown("---")
        st.subheader("📁 Categorías Existentes")
        
        categorias = obtener_categorias()
        if categorias:
            for cat in categorias:
                col1, col2, col3 = st.columns([5, 1, 1])
                with col1:
                    st.write(f"📁 **{cat['nombre']}**")
                with col2:
                    if st.button("✏️", key=f"edit_cat_{cat['id']}", help="Editar"):
                        dialog_editar_categoria(cat['id'], cat['nombre'])
                with col3:
                    if st.button("🗑️", key=f"del_cat_{cat['id']}", help="Eliminar"):
                        dialog_eliminar_categoria(cat['id'], cat['nombre'])
        else:
            st.info("No hay categorías registradas.")

    # --- TAB IMPORTAR ---
    with tab_importar:
        st.subheader("📥 Importar Productos desde Excel")
        st.markdown("Sube tu archivo `AUTOS LED.xlsx`. El sistema leerá la hoja **'LISTA'**.")
        
        archivo = st.file_uploader("Selecciona el archivo Excel", type=["xlsx", "xls"])
        
        if archivo is not None:
            try:
                df_excel = pd.read_excel(archivo, sheet_name="LISTA", skiprows=5)
                df_excel = df_excel.dropna(subset=['CODIGO'])
                df_excel = df_excel[df_excel['CODIGO'] != 'CODIGO']
                
                st.write("Vista previa:")
                st.dataframe(df_excel.head(5), use_container_width=True)
                
                categorias = obtener_categorias()
                cat_importar = st.selectbox("Categoría a asignar:", categorias, format_func=lambda x: x['nombre'])
                
                if st.button("🚀 Iniciar Importación", type="primary"):
                    progreso = st.progress(0)
                    exitosos = 0
                    
                    for index, row in df_excel.iterrows():
                        try:
                            sku = str(row['CODIGO']).strip()
                            nombre = str(row['DESCRIPCION']).strip()
                            stock = int(row['CANTIDAD']) if pd.notna(row['CANTIDAD']) else 0
                            precio = float(row['PRECIO']) if pd.notna(row['PRECIO']) else 0.0
                            costo_estimado = round(precio * 0.6, 2)
                            
                            data = {
                                "sku": sku, "nombre": nombre, "marca": "Genérico",
                                "categoria_id": cat_importar['id'],
                                "precio_usd": precio, "costo_usd": costo_estimado,
                                "stock_actual": stock, "stock_minimo": 2
                            }
                            supabase.table("productos").insert(data).execute()
                            exitosos += 1
                        except:
                            pass
                        progreso.progress((index + 1) / len(df_excel))
                    
                    st.success(f"¡Importación completada! {exitosos} productos cargados.")
                    st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
