import streamlit as st

from app.db import supabase
from app import utils as U


def render():
    st.title("⚙️ Configuración")
    cfg = U.obtener_config(supabase)
    usuario = st.session_state.get("usuario")
    email = getattr(usuario, "email", None)
    admin = U.es_admin(cfg, email)
    if not admin:
        st.info("Solo los administradores pueden modificar la configuración.")

    with st.form("form_config"):
        st.subheader("🏢 Empresa (aparece en el comprobante)")
        c1, c2 = st.columns(2)
        nombre = c1.text_input("Razón social", cfg["empresa_nombre"])
        rif = c2.text_input("RIF", cfg["empresa_rif"])
        direccion = st.text_input("Dirección fiscal", cfg["empresa_direccion"])
        telefono = st.text_input("Teléfono", cfg["empresa_telefono"])

        st.subheader("🧾 Impuestos")
        c1, c2, c3 = st.columns(3)
        iva = c1.number_input("IVA general (%)", 0.0, 100.0, float(cfg["iva_porcentaje"]), 1.0)
        igtf_activo = c2.toggle("Cobrar IGTF (Contribuyente Especial)", U.es_verdadero(cfg["igtf_activo"]))
        igtf = c3.number_input("IGTF (%)", 0.0, 100.0, float(cfg["igtf_porcentaje"]), 0.5)
        iva_defecto = st.toggle("Las ventas nuevas arrancan CON IVA",
                                U.es_verdadero(cfg.get("iva_por_defecto", "true")),
                                help="Apágalo si la mayoría de tus ventas son notas de entrega sin IVA. "
                                     "El cajero igual puede cambiarlo en cada venta.")
        st.caption("El IGTF solo se calcula sobre la parte de la factura pagada en divisas, "
                   "y solo si la empresa es Contribuyente Especial.")

        st.subheader("🛒 Punto de venta")
        c1, c2, c3 = st.columns(3)
        serie = c1.text_input("Prefijo de documentos", cfg["serie_documento"], max_chars=6)
        desc_max = c2.number_input("Descuento máximo por línea (%)", 0.0, 100.0, float(cfg["descuento_max_pct"]), 1.0)
        dias = c3.number_input("Antigüedad máxima de la tasa (días)", 1, 15, int(cfg["tasa_dias_max"]))
        sin_stock = st.toggle("Permitir vender sin stock (no recomendado)", U.es_verdadero(cfg["permitir_venta_sin_stock"]))
        st.subheader("📥 Compras y costos")
        c1, c2 = st.columns(2)
        metodo = c1.radio("¿Cómo se actualiza el costo al comprar?", ["ULTIMO", "PROMEDIO"],
                          index=0 if cfg.get("metodo_costo", "ULTIMO").upper() == "ULTIMO" else 1,
                          format_func=lambda m: "Último costo de compra" if m == "ULTIMO" else "Costo promedio ponderado",
                          help="Último: el costo pasa a ser el de la compra más reciente. "
                               "Promedio: mezcla el costo del stock que tenías con el de la nueva compra.")
        prorratear = c2.toggle("Repartir flete y otros gastos en el costo de los productos",
                               U.es_verdadero(cfg.get("prorratear_gastos", "true")))
        admins = st.text_input("Correos administradores (separados por coma)", cfg["emails_administradores"],
                               help="Pueden anular ventas y cambiar esta configuración. Vacío = todos los usuarios.")
        leyenda = st.text_area("Leyenda del comprobante", cfg["leyenda_documento"])

        if st.form_submit_button("💾 Guardar configuración", type="primary", disabled=not admin):
            if admins.strip() and email and email.lower() not in admins.lower():
                st.error("Incluye tu propio correo en la lista de administradores para no perder el acceso.")
            else:
                valores = {
                    "empresa_nombre": nombre.strip().upper(), "empresa_rif": rif.strip().upper(),
                    "empresa_direccion": direccion.strip(), "empresa_telefono": telefono.strip(),
                    "iva_porcentaje": f"{iva:g}", "iva_por_defecto": str(iva_defecto).lower(), "igtf_activo": str(igtf_activo).lower(),
                    "igtf_porcentaje": f"{igtf:g}", "serie_documento": serie.strip().upper() or "NE",
                    "descuento_max_pct": f"{desc_max:g}", "tasa_dias_max": str(int(dias)),
                    "permitir_venta_sin_stock": str(sin_stock).lower(),
                    "metodo_costo": metodo, "prorratear_gastos": str(prorratear).lower(),
                    "emails_administradores": admins.strip(), "leyenda_documento": leyenda.strip(),
                }
                try:
                    supabase.table("configuracion").upsert(
                        [{"clave": k, "valor": v} for k, v in valores.items()], on_conflict="clave").execute()
                    st.success("Configuración guardada.")
                except Exception as e:
                    st.error(U.mensaje_error(e))
