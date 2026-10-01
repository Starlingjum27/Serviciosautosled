import streamlit as st
from app.db import supabase
import datetime

def obtener_ultima_tasa():
    try:
        res = supabase.table("tasas_bcv").select("tasa").order("fecha", desc=True).limit(1).execute()
        if res.data:
            return res.data[0]['tasa']
    except:
        pass
    return 0.0

def generar_numero_factura():
    """Genera un número de factura correlativo."""
    try:
        res = supabase.table("ventas").select("id").order("id", desc=True).limit(1).execute()
        ultimo_id = res.data[0]['id'] if res.data else 0
        return f"FAC-{ultimo_id + 1:06d}"
    except:
        return "FAC-000001"

def render():
    st.title("🛒 Punto de Venta (Facturación)")
    tasa_actual = obtener_ultima_tasa()
    
    if tasa_actual == 0.0:
        st.error("⚠️ No hay tasa BCV registrada. Ve al módulo 'Tasa BCV' primero.")
        return
    
    st.info(f"💱 Tasa BCV aplicada: **Bs. {tasa_actual:.2f}**")

    # Inicializar el carrito en la sesión
    if 'carrito' not in st.session_state:
        st.session_state.carrito = []

    # --- 1. BUSCADOR DE PRODUCTOS ---
    st.subheader("🔍 Buscar Producto")
    busqueda = st.text_input("Escribe el SKU o Nombre del producto", key="busqueda_pos")
    
    if busqueda:
        try:
            res = supabase.table("productos").select("*").or_(f"sku.ilike.%{busqueda}%,nombre.ilike.%{busqueda}%").limit(5).execute()
            if res.data:
                opciones = {f"{p['sku']} - {p['nombre']} (${p['precio_usd']})": p for p in res.data}
                prod_sel = st.selectbox("Selecciona el producto", list(opciones.keys()))
                
                if prod_sel:
                    producto = opciones[prod_sel]
                    col1, col2 = st.columns([1, 4])
                    with col1:
                        cantidad = st.number_input("Cantidad", min_value=1, value=1, step=1)
                    with col2:
                        st.write("") # Espacio
                        st.write("") # Espacio
                        if st.button("➕ Agregar al Carrito", type="primary"):
                            if cantidad > producto['stock_actual']:
                                st.error(f"Stock insuficiente. Solo quedan {producto['stock_actual']} unidades.")
                            else:
                                # Agregar al carrito
                                st.session_state.carrito.append({
                                    "producto_id": producto['id'],
                                    "sku": producto['sku'],
                                    "nombre": producto['nombre'],
                                    "cantidad": cantidad,
                                    "precio_usd": float(producto['precio_usd']),
                                    "costo_usd": float(producto['costo_usd']),
                                    "subtotal_usd": float(producto['precio_usd']) * cantidad
                                })
                                st.success(f"Agregado: {producto['nombre']}")
                                st.rerun()
            else:
                st.warning("No se encontraron productos con ese criterio.")
        except Exception as e:
            st.error(f"Error en búsqueda: {e}")

    st.markdown("---")

    # --- 2. CARRITO DE COMPRAS ---
    st.subheader("🛒 Carrito de Compras")
    
    if not st.session_state.carrito:
        st.info("El carrito está vacío. Busca productos arriba para agregar.")
    else:
        # Mostrar items del carrito
        for i, item in enumerate(st.session_state.carrito):
            col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
            with col1:
                st.write(f"**{item['nombre']}** ({item['sku']})")
            with col2:
                st.write(f"Cant: {item['cantidad']}")
            with col3:
                st.write(f"${item['precio_usd']:.2f}")
            with col4:
                st.write(f"**${item['subtotal_usd']:.2f}**")
            with col5:
                if st.button("❌", key=f"del_{i}"):
                    st.session_state.carrito.pop(i)
                    st.rerun()

        # --- 3. CÁLCULOS FISCALES ---
        subtotal_usd = sum(item['subtotal_usd'] for item in st.session_state.carrito)
        subtotal_bs = subtotal_usd * tasa_actual
        
        # IVA 16%
        iva_usd = subtotal_usd * 0.16
        iva_bs = iva_usd * tasa_actual
        
        # IGTF 3% (Configurable, por defecto lo calculamos sobre el total)
        igtf_usd = subtotal_usd * 0.03
        igtf_bs = igtf_usd * tasa_actual
        
        total_usd = subtotal_usd + iva_usd + igtf_usd
        total_bs = total_usd * tasa_actual

        st.markdown("### Resumen de Pago")
        col_res1, col_res2 = st.columns(2)
        with col_res1:
            st.write(f"Subtotal (USD): **${subtotal_usd:.2f}**")
            st.write(f"IVA 16% (USD): **${iva_usd:.2f}**")
            st.write(f"IGTF 3% (USD): **${igtf_usd:.2f}**")
            st.write(f"**TOTAL (USD): ${total_usd:.2f}**")
        with col_res2:
            st.write(f"Subtotal (Bs): **Bs. {subtotal_bs:.2f}**")
            st.write(f"IVA 16% (Bs): **Bs. {iva_bs:.2f}**")
            st.write(f"IGTF 3% (Bs): **Bs. {igtf_bs:.2f}**")
            st.write(f"**TOTAL (Bs): Bs. {total_bs:.2f}**")

        st.markdown("---")
        
        # --- 4. DATOS DEL CLIENTE Y CIERRE ---
        col_cliente1, col_cliente2 = st.columns(2)
        with col_cliente1:
            cliente_nombre = st.text_input("Nombre del Cliente", value="Cliente Final")
        with col_cliente2:
            cliente_rif = st.text_input("RIF / Cédula", value="V-00000000")
        
        metodo_pago = st.selectbox("Método de Pago", ["Efectivo Bs", "Pago Móvil", "Punto de Venta", "Efectivo USD", "Transferencia"])

        if st.button("💳 Finalizar Venta y Facturar", type="primary", use_container_width=True):
            try:
                numero_factura = generar_numero_factura()
                usuario_id = st.session_state.usuario.id if st.session_state.get('usuario') else None
                
                # 1. Insertar Cabecera de Venta
                venta_data = {
                    "numero_factura": numero_factura,
                    "cliente_nombre": cliente_nombre,
                    "cliente_rif": cliente_rif,
                    "tasa_bcv": tasa_actual,
                    "subtotal_usd": subtotal_usd,
                    "iva_usd": iva_usd,
                    "igtf_usd": igtf_usd,
                    "total_usd": total_usd,
                    "total_bs": total_bs,
                    "metodo_pago": metodo_pago,
                    "usuario_id": usuario_id
                }
                res_venta = supabase.table("ventas").insert(venta_data).execute()
                venta_id = res_venta.data[0]['id']
                
                # 2. Insertar Detalle y Descontar Stock
                for item in st.session_state.carrito:
                    # Insertar detalle
                    detalle_data = {
                        "venta_id": venta_id,
                        "producto_id": item['producto_id'],
                        "cantidad": item['cantidad'],
                        "precio_usd": item['precio_usd'],
                        "subtotal_usd": item['subtotal_usd']
                    }
                    supabase.table("detalle_ventas").insert(detalle_data).execute()
                    
                    # Actualizar Stock
                    prod_actual = supabase.table("productos").select("stock_actual").eq("id", item['producto_id']).execute().data[0]
                    nuevo_stock = prod_actual['stock_actual'] - item['cantidad']
                    supabase.table("productos").update({"stock_actual": nuevo_stock}).eq("id", item['producto_id']).execute()
                    
                    # Registrar Movimiento de Inventario (Kardex)
                    mov_data = {
                        "producto_id": item['producto_id'],
                        "tipo": "Salida",
                        "cantidad": item['cantidad'],
                        "costo_usd": item['costo_usd'],
                        "tasa_bcv": tasa_actual,
                        "equivalente_bs": item['costo_usd'] * tasa_actual * item['cantidad'],
                        "documento_origen": "Venta",
                        "documento_id": str(venta_id),
                        "usuario_id": usuario_id
                    }
                    supabase.table("movimientos_inventario").insert(mov_data).execute()

                st.success(f"✅ ¡Venta exitosa! Factura N° {numero_factura}")
                st.balloons()
                
                # Limpiar carrito
                st.session_state.carrito = []
                st.rerun()
                
            except Exception as e:
                st.error(f"Error al procesar la venta: {e}")
