"""
PRODUCTOS · catálogo, edición, categorías (opcionales) y carga masiva desde Excel.
Si en Configuración se desactiva "Usar categorías", desaparecen la pestaña de categorías,
los filtros y el campo categoría; el SKU se genera con el prefijo PRD-.
"""
import re
import unicodedata

import pandas as pd
import streamlit as st

from app.db import supabase
from app import utils as U

PREFIJO_GENERAL = "PRD"
PREFIJO_SERVICIO = "SRV"
TIPOS = {"PRODUCTO": "📦 Producto (lleva inventario)", "SERVICIO": "🛠️ Servicio / mano de obra (sin inventario)"}


def es_servicio(prod) -> bool:
    """Acepta dict o fila de pandas."""
    return str((prod.get("tipo") if hasattr(prod, "get") else None) or "PRODUCTO").upper() == "SERVICIO"


# =====================================================================
# AUXILIARES (compras.py también usa obtener_categorias y generar_sku)
# =====================================================================
def usa_categorias() -> bool:
    cfg = st.session_state.get("_cfg_prod")
    if cfg is None:
        cfg = U.obtener_config(supabase)
    return U.es_verdadero(cfg.get("usar_categorias", "true"))


def obtener_categorias():
    try:
        res = supabase.table("categorias").select("id, nombre").order("nombre").execute()
        return res.data or []
    except Exception:
        return []


def generar_sku(nombre_categoria: str | None = None, servicio: bool = False) -> str:
    """Prefijo de 3 letras de la categoría (o PRD; SRV para servicios) + siguiente número libre: LED-0007, SRV-0003."""
    if servicio:
        prefijo = PREFIJO_SERVICIO
    elif nombre_categoria:
        texto = unicodedata.normalize("NFKD", nombre_categoria).encode("ASCII", "ignore").decode("utf-8")
        texto = re.sub(r"[^A-Z0-9]", "", texto.upper())
        prefijo = texto[:3].ljust(3, "X")
    else:
        prefijo = PREFIJO_GENERAL
    try:
        res = supabase.table("productos").select("sku").ilike("sku", f"{prefijo}-%").execute()
        numeros = [int(m.group(1)) for r in (res.data or [])
                   if (m := re.fullmatch(rf"{prefijo}-(\d+)", str(r["sku"]).upper()))]
        return f"{prefijo}-{(max(numeros) if numeros else 0) + 1:04d}"
    except Exception:
        return f"{prefijo}-0001"


def _selector_categoria(categorias, actual_id=None):
    if not categorias:
        st.caption("No hay categorías creadas: el producto quedará sin categoría.")
        return None
    opciones = [None] + categorias
    idx = next((i for i, c in enumerate(opciones) if c and c["id"] == actual_id), 0)
    return st.selectbox("Categoría", opciones, index=idx,
                        format_func=lambda c: "Sin categoría" if c is None else c["nombre"])


# =====================================================================
# VENTANAS
# =====================================================================
@st.dialog("➕ Nuevo producto o servicio")
def dialog_nuevo_producto():
    tipo = st.radio("¿Qué vas a registrar?", list(TIPOS), format_func=TIPOS.get, horizontal=True)
    servicio = tipo == "SERVICIO"
    usar = usa_categorias()
    categoria = _selector_categoria(obtener_categorias()) if usar else None
    sku_auto = generar_sku(categoria["nombre"] if categoria else None, servicio=servicio)
    st.info(f"🔢 Código que se asignará: **{sku_auto}**")

    nombre = st.text_input("Nombre del servicio *" if servicio else "Nombre del producto *",
                           placeholder="Ej: Instalación de faros LED" if servicio else "")
    marca = "" if servicio else st.text_input("Marca")
    col1, col2 = st.columns(2)
    precio_usd = col1.number_input("Precio de venta (USD)" + ("" if servicio else " *"),
                                   min_value=0.0, step=0.01, format="%.2f",
                                   help="Déjalo en 0 si el precio se decide en cada trabajo: se escribe al vender."
                                   if servicio else None)
    costo_usd = col1.number_input("Costo (USD)", min_value=0.0, step=0.01, format="%.2f",
                                  help="Lo que te cuesta hacerlo (ej. pago al técnico). Opcional." if servicio else None)
    if servicio:
        stock_actual, stock_minimo = 0, 0
        col2.caption("🛠️ Los servicios no llevan inventario: no se compran ni se descuentan del stock.")
    else:
        stock_actual = col2.number_input("Stock inicial", min_value=0, step=1)
        stock_minimo = col2.number_input("Stock mínimo", min_value=0, step=1, value=5)
    exento = st.checkbox("Exento de IVA")
    if precio_usd > 0 and costo_usd > 0:
        m = U.margen_pct(precio_usd, costo_usd)
        st.caption(f"Margen de ganancia: **{U.fmt_num(m, 1)}%**")

    st.divider()
    col_g, col_c = st.columns(2)
    if col_c.button("Cancelar", use_container_width=True):
        st.rerun()
    if col_g.button("💾 Guardar", use_container_width=True, type="primary"):
        if not nombre.strip() or (precio_usd <= 0 and not servicio):
            st.error("El nombre y el precio de venta son obligatorios.")
            return
        try:
            supabase.table("productos").insert({
                "sku": sku_auto, "nombre": nombre.strip(), "marca": marca.strip() or None,
                "categoria_id": categoria["id"] if categoria else None, "tipo": tipo,
                "precio_usd": precio_usd, "costo_usd": costo_usd, "stock_actual": int(stock_actual),
                "stock_minimo": int(stock_minimo), "exento_iva": exento, "activo": True,
            }).execute()
        except Exception as e:
            st.error(U.mensaje_error(e))
            return
        st.toast(f"{'Servicio' if servicio else 'Producto'} {sku_auto} guardado ✅")
        st.rerun()


@st.dialog("✏️ Editar producto")
def dialog_editar_producto(id_prod):
    try:
        datos = supabase.table("productos").select("*").eq("id", id_prod).single().execute().data
    except Exception:
        st.error("No se pudo cargar el producto.")
        return

    st.markdown(f"**Código:** `{datos['sku']}`")
    stock_guardado = int(datos.get("stock_actual") or 0)
    tipo_actual = "SERVICIO" if es_servicio(datos) else "PRODUCTO"
    n_tipo = st.radio("Tipo", list(TIPOS), index=list(TIPOS).index(tipo_actual), format_func=TIPOS.get,
                      horizontal=True, disabled=stock_guardado != 0,
                      help="Para convertirlo en servicio primero debe quedar en 0 unidades." if stock_guardado else None)
    servicio = n_tipo == "SERVICIO"
    usar = usa_categorias()
    categoria = _selector_categoria(obtener_categorias(), datos.get("categoria_id")) if usar else None
    n_nombre = st.text_input("Nombre", value=datos["nombre"])
    n_marca = st.text_input("Marca", value=datos.get("marca") or "")
    col1, col2 = st.columns(2)
    n_precio = col1.number_input("Precio USD", value=float(datos.get("precio_usd") or 0), min_value=0.0, step=0.01, format="%.2f",
                                 help="En 0 el precio se escribe en cada venta." if servicio else None)
    n_costo = col1.number_input("Costo USD", value=float(datos.get("costo_usd") or 0), min_value=0.0, step=0.01, format="%.2f")
    if servicio:
        n_stock, n_minimo = 0, 0
        col2.caption("🛠️ Servicio: no lleva inventario.")
    else:
        n_stock = col2.number_input("Stock actual", value=stock_guardado, min_value=0, step=1,
                                    help="Si lo cambias, queda registrado en el Kardex como ajuste manual.")
        n_minimo = col2.number_input("Stock mínimo", value=int(datos.get("stock_minimo") or 0), min_value=0, step=1)
    c3, c4 = st.columns(2)
    n_exento = c3.checkbox("Exento de IVA", value=bool(datos.get("exento_iva")))
    n_activo = c4.checkbox("Activo (se puede vender y comprar)", value=bool(datos.get("activo", True)))
    if not servicio and n_stock != stock_guardado:
        st.warning("Para entradas de mercancía usa el módulo **📥 Compras**: así se registra el costo y el proveedor.")

    st.divider()
    col_g, col_c = st.columns(2)
    if col_c.button("Cancelar", use_container_width=True):
        st.rerun()
    if col_g.button("💾 Guardar cambios", use_container_width=True, type="primary"):
        if not n_nombre.strip():
            st.error("El nombre es obligatorio.")
            return
        if not servicio and n_precio <= 0:
            st.error("Un producto necesita precio de venta.")
            return
        cambios = {"nombre": n_nombre.strip(), "marca": n_marca.strip() or None, "precio_usd": n_precio,
                   "costo_usd": n_costo, "stock_actual": int(n_stock), "stock_minimo": int(n_minimo),
                   "exento_iva": n_exento, "activo": n_activo, "tipo": n_tipo}
        if usar:
            cambios["categoria_id"] = categoria["id"] if categoria else None
        try:
            supabase.table("productos").update(cambios).eq("id", id_prod).execute()
        except Exception as e:
            st.error(U.mensaje_error(e))
            return
        st.toast("Producto actualizado ✅")
        st.rerun()


@st.dialog("🗑️ Eliminar producto")
def dialog_eliminar_producto(id_prod, sku, nombre):
    st.warning("¿Eliminar este producto? Esta acción no se puede deshacer.")
    st.markdown(f"**{sku}** · {nombre}")
    col1, col2 = st.columns(2)
    if col2.button("Cancelar", use_container_width=True):
        st.rerun()
    if col1.button("🗑️ Sí, eliminar", use_container_width=True, type="primary"):
        try:
            r = supabase.table("productos").delete().eq("id", id_prod).execute()
        except Exception as e:
            msg = U.mensaje_error(e)
            if "foreign key" in msg.lower() or "violates" in msg.lower():
                st.error("Este producto tiene ventas, compras o movimientos registrados y no se puede borrar. "
                         "Desactívalo desde **✏️ Editar** para que no aparezca más.")
            else:
                st.error(msg)
            return
        if not r.data:  # la base de datos no borró nada (permisos)
            st.error(U.MSG_SOLO_ADMIN)
            return
        st.toast("Producto eliminado")
        st.rerun()


@st.dialog("✏️ Editar categoría")
def dialog_editar_categoria(id_cat, nombre_actual):
    nuevo_nombre = st.text_input("Nuevo nombre", value=nombre_actual)
    col1, col2 = st.columns(2)
    if col2.button("Cancelar", use_container_width=True):
        st.rerun()
    if col1.button("💾 Guardar", use_container_width=True, type="primary") and nuevo_nombre.strip():
        try:
            supabase.table("categorias").update({"nombre": nuevo_nombre.strip()}).eq("id", id_cat).execute()
        except Exception as e:
            st.error(U.mensaje_error(e))
            return
        st.rerun()


@st.dialog("🗑️ Eliminar categoría")
def dialog_eliminar_categoria(id_cat, nombre):
    asociados = supabase.table("productos").select("id").eq("categoria_id", id_cat).execute().data or []
    if asociados:
        st.error(f"No se puede eliminar **{nombre}**: tiene {len(asociados)} producto(s) asociados.")
        if st.button("Cerrar", use_container_width=True):
            st.rerun()
        return
    st.warning(f"¿Eliminar la categoría **{nombre}**?")
    col1, col2 = st.columns(2)
    if col2.button("Cancelar", use_container_width=True):
        st.rerun()
    if col1.button("🗑️ Sí, eliminar", use_container_width=True, type="primary"):
        try:
            r = supabase.table("categorias").delete().eq("id", id_cat).execute()
        except Exception as e:
            st.error(U.mensaje_error(e))
            return
        if not r.data:  # la base de datos no borró nada (permisos)
            st.error(U.MSG_SOLO_ADMIN)
            return
        st.rerun()


# =====================================================================
# PESTAÑAS
# =====================================================================
def _tab_catalogo(usar, tasa):
    c1, c2 = st.columns([3, 1])
    if c2.button("➕ Nuevo", type="primary", use_container_width=True, help="Producto o servicio"):
        dialog_nuevo_producto()
    with c1:
        st.caption("Busca, revisa el stock y edita tus productos y servicios.")

    if usar:
        col_busq, col_filtro, col_tipo, col_estado = st.columns([3, 2, 2, 2])
        filtro_cat = col_filtro.selectbox("Categoría", ["Todas"] + [c["nombre"] for c in obtener_categorias()])
    else:
        col_busq, col_tipo, col_estado = st.columns([4, 2, 2])
        filtro_cat = "Todas"
    busqueda = col_busq.text_input("Buscar por código, nombre o marca", "")
    filtro_tipo = col_tipo.selectbox("Tipo", ["Todos", "Productos", "Servicios"])
    ver = col_estado.selectbox("Mostrar", ["Activos", "Todos", "Inactivos"])

    try:
        productos = supabase.table("productos").select("*").order("nombre").execute().data or []
        categorias = {c["id"]: c["nombre"] for c in obtener_categorias()} if usar else {}
    except Exception as e:
        st.error(f"Error cargando inventario: {U.mensaje_error(e)}")
        return
    if not productos:
        st.info("No hay productos registrados. Presiona **➕ Nuevo producto** o usa la carga masiva.")
        return

    df = pd.DataFrame(productos)
    for col, defecto in (("activo", True), ("marca", ""), ("stock_minimo", 0), ("categoria_id", None),
                         ("tipo", "PRODUCTO")):
        if col not in df.columns:
            df[col] = defecto
    df["activo"] = df["activo"].fillna(True).astype(bool)
    df["servicio"] = df["tipo"].fillna("PRODUCTO").astype(str).str.upper().eq("SERVICIO")
    if filtro_tipo == "Productos":
        df = df[~df["servicio"]]
    elif filtro_tipo == "Servicios":
        df = df[df["servicio"]]
    df["categoria"] = df["categoria_id"].map(lambda i: categorias.get(i, "Sin categoría"))
    if ver == "Activos":
        df = df[df["activo"]]
    elif ver == "Inactivos":
        df = df[~df["activo"]]
    if busqueda:
        mask = df[["sku", "nombre", "marca"]].astype(str).apply(
            lambda x: x.str.contains(busqueda, case=False, na=False, regex=False)).any(axis=1)
        df = df[mask]
    if filtro_cat != "Todas":
        df = df[df["categoria"] == filtro_cat]
    if df.empty:
        st.info("No se encontraron productos con ese criterio.")
        return

    def alerta(row):
        stock, minimo = row["stock_actual"] or 0, row["stock_minimo"] or 0
        if not row["activo"]:
            return "🚫 Inactivo"
        if row["servicio"]:
            return "🛠️ Servicio"
        if stock <= 0:
            return "❌ Agotado"
        return "⚠️ Bajo" if stock <= minimo else "✅ OK"

    tabla = pd.DataFrame({
        "SKU": df["sku"], "Producto": df["nombre"], "Marca": df["marca"].fillna(""),
        **({"Categoría": df["categoria"]} if usar else {}),
        "Stock": df.apply(lambda r: "—" if r["servicio"] else str(int(r["stock_actual"] or 0)), axis=1),
        "Estado": df.apply(alerta, axis=1),
        "Precio $": df["precio_usd"].astype(float),
        "Precio Bs": (df["precio_usd"].astype(float) * float(tasa)) if tasa else 0.0,
    })
    st.dataframe(tabla, use_container_width=True, hide_index=True, column_config={
        "Precio $": st.column_config.NumberColumn(format="%.2f"),
        "Precio Bs": st.column_config.NumberColumn(format="%.2f"),
    })
    n_serv = int(df["servicio"].sum())
    st.caption(f"{len(tabla) - n_serv} producto(s)" + (f" · {n_serv} servicio(s)" if n_serv else ""))

    st.markdown("#### 🛠️ Editar o eliminar")
    admin = U.es_admin_actual(supabase)
    for _, p in df.head(30).iterrows():
        col_info, col_edit, col_del = st.columns([6, 1, 1])
        col_info.write(f"`{p['sku']}` — {p['nombre']}" + ("  ·  🛠️" if p["servicio"] else "")
                       + ("" if p["activo"] else "  ·  🚫"))
        if col_edit.button("✏️", key=f"btn_edit_{p['id']}", help="Editar"):
            dialog_editar_producto(p["id"])
        if col_del.button("🗑️", key=f"btn_del_{p['id']}", disabled=not admin,
                          help="Eliminar" if admin else "Solo un administrador puede eliminar"):
            dialog_eliminar_producto(p["id"], p["sku"], p["nombre"])
    if len(df) > 30:
        st.caption("Se muestran los primeros 30. Usa el buscador para encontrar el que necesitas.")


def _tab_categorias():
    st.subheader("➕ Crear categoría")
    with st.form("nueva_cat_form", clear_on_submit=True):
        col_input, col_btn = st.columns([3, 1])
        nueva = col_input.text_input("Nombre", label_visibility="collapsed", placeholder="Ej: Iluminación LED, Sensores...")
        if col_btn.form_submit_button("➕ Agregar", use_container_width=True) and nueva.strip():
            try:
                supabase.table("categorias").insert({"nombre": nueva.strip()}).execute()
                st.rerun()
            except Exception as e:
                st.error(U.mensaje_error(e))
    st.subheader("📁 Categorías existentes")
    categorias = obtener_categorias()
    if not categorias:
        st.info("No hay categorías registradas.")
    admin = U.es_admin_actual(supabase)
    for cat in categorias:
        col1, col2, col3 = st.columns([5, 1, 1])
        col1.write(f"📁 **{cat['nombre']}**")
        if col2.button("✏️", key=f"edit_cat_{cat['id']}", help="Editar"):
            dialog_editar_categoria(cat["id"], cat["nombre"])
        if col3.button("🗑️", key=f"del_cat_{cat['id']}", disabled=not admin,
                       help="Eliminar" if admin else "Solo un administrador puede eliminar"):
            dialog_eliminar_categoria(cat["id"], cat["nombre"])


def _tab_importar(usar):
    st.subheader("📥 Importar productos desde Excel")
    st.markdown("Sube tu archivo `AUTOS LED.xlsx`. El sistema leerá la hoja **'LISTA'**.")
    archivo = st.file_uploader("Selecciona el archivo Excel", type=["xlsx", "xls"])
    if archivo is None:
        return
    try:
        df_excel = pd.read_excel(archivo, sheet_name="LISTA", skiprows=5)
        # Se conservan las filas SIN código (se les genera uno PRD-0001…); solo se descartan las vacías
        df_excel = df_excel.dropna(subset=["DESCRIPCION"])
        df_excel = df_excel[df_excel["DESCRIPCION"].astype(str).str.strip().ne("")]
        df_excel = df_excel[df_excel["CODIGO"].astype(str).str.upper() != "CODIGO"]
    except Exception as e:
        st.error(f"No se pudo leer el archivo: {e}")
        return
    sin_codigo = int(df_excel["CODIGO"].isna().sum())
    st.write(f"Se encontraron **{len(df_excel)}** productos"
             + (f", de ellos **{sin_codigo} sin código** (se les asignará uno automático)." if sin_codigo else "."))
    st.write("Vista previa:")
    st.dataframe(df_excel.head(5), use_container_width=True)

    categoria = None
    if usar:
        categoria = _selector_categoria(obtener_categorias())
    st.caption("El costo se estima en 60% del precio. Se reemplazará por el costo real con cada compra que registres.")

    if st.button("🚀 Iniciar importación", type="primary"):
        progreso = st.progress(0.0)
        exitosos, fallidos = 0, []
        total = len(df_excel)
        for n, (_, row) in enumerate(df_excel.iterrows(), start=1):
            try:
                if pd.notna(row["CODIGO"]) and str(row["CODIGO"]).strip():
                    sku = re.sub(r"\s+", "", str(row["CODIGO"])).upper()
                else:
                    sku = generar_sku(categoria["nombre"] if categoria else None)
                precio = float(row["PRECIO"]) if pd.notna(row["PRECIO"]) else 0.0
                supabase.table("productos").insert({
                    "sku": sku, "nombre": re.sub(r"\s+", " ", str(row["DESCRIPCION"])).strip(), "marca": None,
                    "categoria_id": categoria["id"] if categoria else None,
                    "precio_usd": precio, "costo_usd": round(precio * 0.6, 2),
                    "stock_actual": int(row["CANTIDAD"]) if pd.notna(row["CANTIDAD"]) else 0,
                    "stock_minimo": 2, "activo": True,
                }).execute()
                exitosos += 1
            except Exception:
                fallidos.append(str(row["CODIGO"]) if pd.notna(row["CODIGO"]) else str(row["DESCRIPCION"])[:30])
            progreso.progress(n / total)
        st.success(f"Importación completada: {exitosos} producto(s) cargados.")
        if fallidos:
            st.warning(f"{len(fallidos)} no se cargaron (probablemente el SKU ya existe): "
                       + ", ".join(fallidos[:15]) + ("…" if len(fallidos) > 15 else ""))


# =====================================================================
def render():
    cfg = U.obtener_config(supabase)
    st.session_state._cfg_prod = cfg
    usar = U.es_verdadero(cfg.get("usar_categorias", "true"))
    _, tasa = U.tasa_vigente(supabase)

    st.title("📦 Productos")
    if tasa:
        st.caption(f"💱 Precios en Bs calculados con la tasa BCV vigente: **Bs. {U.fmt_num(tasa, 4)}**")
    else:
        st.warning("⚠️ No hay tasa BCV registrada.")

    if usar:
        tab_cat, tab_categorias, tab_imp = st.tabs(["📋 Catálogo", "📁 Categorías", "📥 Carga masiva (Excel)"])
        with tab_categorias:
            _tab_categorias()
    else:
        tab_cat, tab_imp = st.tabs(["📋 Catálogo", "📥 Carga masiva (Excel)"])
    with tab_cat:
        _tab_catalogo(usar, tasa)
    with tab_imp:
        _tab_importar(usar)
