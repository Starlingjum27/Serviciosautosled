"""
CONFIGURACIÓN · versión guiada
================================
  🧭 Asistente paso a paso: Empresa → Impuestos → Tasa BCV → Ventas → Compras → Seguridad → Revisar
  🗂️ Tarjetas por sección: cada una muestra los valores actuales y abre su propia ventana de edición.
  🧾 Vista previa del comprobante con los datos de la empresa.
"""
from html import escape

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from app.db import supabase
from app import utils as U
from app.comprobante import generar_html
from app.modules.ventas import CSS, _pasos

SECCIONES = [
    ("empresa", "🏢", "Empresa", "Datos fiscales que aparecen en tus comprobantes"),
    ("impuestos", "🧾", "Impuestos", "IVA de tus ventas e IGTF sobre pagos en divisas"),
    ("tasa", "💱", "Tasa BCV", "Actualización automática y vigencia de la tasa"),
    ("ventas", "🛒", "Punto de venta", "Numeración, descuentos y control de stock"),
    ("compras", "📥", "Compras y costos", "Cómo se calcula el costo de tus productos"),
    ("seguridad", "🔐", "Seguridad", "Quién puede anular documentos y cambiar la configuración"),
]

ETIQUETAS = {
    "empresa_nombre": "Razón social", "empresa_rif": "RIF", "empresa_direccion": "Dirección fiscal",
    "empresa_telefono": "Teléfono", "leyenda_documento": "Leyenda del comprobante",
    "iva_porcentaje": "IVA (%)", "iva_por_defecto": "Ventas nuevas con IVA", "igtf_activo": "Cobrar IGTF",
    "igtf_porcentaje": "IGTF (%)", "tasa_automatica": "Tasa automática", "tasa_dias_max": "Días máx. de la tasa",
    "serie_documento": "Prefijo de documentos", "descuento_max_pct": "Descuento máximo (%)",
    "permitir_venta_sin_stock": "Vender sin stock", "metodo_costo": "Método de costo",
    "prorratear_gastos": "Repartir flete en el costo", "emails_administradores": "Administradores",
}


def _si_no(valor) -> str:
    return "Sí" if U.es_verdadero(valor) else "No"


def _email() -> str:
    usuario = st.session_state.get("usuario")
    return (getattr(usuario, "email", "") or "").lower()


def _admins(texto: str) -> list[str]:
    return [x.strip().lower() for x in texto.replace("\n", ",").replace(";", ",").split(",") if x.strip()]


# =====================================================================
# FORMULARIOS (uno por sección; se usan en el asistente y en las ventanas)
# Cada uno recibe el borrador y devuelve (valores, error)
# =====================================================================
def _form_empresa(b: dict):
    st.info("Estos datos salen en el encabezado de cada comprobante de venta y de compra.")
    nombre = st.text_input("Razón social *", b["empresa_nombre"])
    actual = b.get("empresa_rif", "")
    letras = ["J", "G", "V", "E", "P"]
    letra = actual[:1] if actual[:1] in letras else "J"
    c1, c2 = st.columns([1, 3])
    letra = c1.selectbox("Tipo", letras, index=letras.index(letra))
    numero = c2.text_input("RIF *", "".join(ch for ch in actual if ch.isdigit()), placeholder="Ej: 123456789")
    rif = U.normalizar_rif(letra, numero) if numero else None
    if rif:
        st.caption(f"Se guardará como **{rif}**")
    direccion = st.text_area("Dirección fiscal *", b["empresa_direccion"], height=70)
    telefono = st.text_input("Teléfono / WhatsApp", b["empresa_telefono"])
    leyenda = st.text_area("Leyenda al pie del comprobante", b["leyenda_documento"], height=70,
                           help="Ej.: condiciones de garantía, o que el documento es no fiscal.")

    st.markdown("**Así se verá el encabezado:**")
    st.markdown(f"""<div style="border:1px dashed rgba(128,128,128,.5); border-radius:12px; padding:.8rem;
        text-align:center; font-family:'Courier New',monospace; font-size:.85rem;">
        <b>{escape(nombre.strip().upper() or 'RAZÓN SOCIAL')}</b><br>RIF: {escape(rif or '—')}<br>
        {escape(direccion.strip() or 'Dirección fiscal')}<br>{escape(telefono.strip())}</div>""",
                unsafe_allow_html=True)

    error = None
    if not nombre.strip():
        error = "Escribe la razón social."
    elif not rif:
        error = "El RIF debe tener entre 5 y 9 dígitos."
    elif not direccion.strip():
        error = "Escribe la dirección fiscal."
    return {"empresa_nombre": nombre.strip().upper(), "empresa_rif": rif or actual,
            "empresa_direccion": direccion.strip(), "empresa_telefono": telefono.strip(),
            "leyenda_documento": leyenda.strip()}, error


def _form_impuestos(b: dict):
    st.markdown("##### IVA")
    c1, c2 = st.columns(2)
    iva = c1.number_input("Alícuota general de IVA (%)", 0.0, 100.0, float(b["iva_porcentaje"]), 1.0)
    iva_def = c2.toggle("Las ventas nuevas arrancan CON IVA", U.es_verdadero(b.get("iva_por_defecto", "true")))
    st.caption("El cajero siempre puede activar o desactivar el IVA en cada venta. "
               "Sin IVA, la venta se emite como **nota de entrega**.")

    st.markdown("##### IGTF")
    igtf_act = st.toggle("Soy Contribuyente Especial: cobrar IGTF sobre pagos en divisas",
                         U.es_verdadero(b["igtf_activo"]))
    igtf = st.number_input("Alícuota IGTF (%)", 0.0, 100.0, float(b["igtf_porcentaje"]), 0.5, disabled=not igtf_act)
    if igtf_act:
        st.caption(f"Ejemplo: si el cliente paga $100 en efectivo, se suma **{U.fmt_usd(igtf)}** de IGTF. "
                   "Los pagos en bolívares no generan IGTF.")
    else:
        st.caption("Con el IGTF desactivado, los pagos en divisas no tienen recargo.")
    return {"iva_porcentaje": f"{iva:g}", "iva_por_defecto": str(iva_def).lower(),
            "igtf_activo": str(igtf_act).lower(), "igtf_porcentaje": f"{igtf:g}"}, None


def _form_tasa(b: dict):
    auto = st.toggle("Actualizar la tasa automáticamente al iniciar sesión (días hábiles)",
                     U.es_verdadero(b.get("tasa_automatica", "true")))
    st.caption("Si la consulta falla o el valor parece anormal (más de 10% de diferencia), "
               "el sistema te avisa para que la registres manualmente. Nunca sobrescribe una tasa ya cargada.")
    dias = st.slider("Días máximos de antigüedad de la tasa para poder vender y comprar", 1, 15,
                     min(max(int(b["tasa_dias_max"]), 1), 15))
    st.caption(f"Si la última tasa registrada tiene más de **{dias} días**, el sistema bloquea ventas y compras "
               "hasta que la actualices. Con 4 días se cubren fines de semana largos.")
    return {"tasa_automatica": str(auto).lower(), "tasa_dias_max": str(int(dias))}, None


def _form_ventas(b: dict):
    serie = st.text_input("Prefijo de los documentos de venta", b["serie_documento"], max_chars=6)
    serie_ok = serie.strip().upper() or "NE"
    st.caption(f"Tus documentos se numerarán así: **{serie_ok}-00000001**, **{serie_ok}-00000002**…")
    desc = st.slider("Descuento máximo que puede dar el cajero por producto (%)", 0, 50,
                     min(max(int(float(b["descuento_max_pct"])), 0), 50))
    st.caption("Con 0% se oculta la opción de descuento en el Punto de Venta.")
    sin_stock = st.toggle("Permitir vender productos sin stock", U.es_verdadero(b["permitir_venta_sin_stock"]))
    if sin_stock:
        st.warning("El inventario podrá quedar en negativo. Úsalo solo si vendes por encargo.")
    return {"serie_documento": serie_ok, "descuento_max_pct": str(desc),
            "permitir_venta_sin_stock": str(sin_stock).lower()}, None


def _form_compras(b: dict):
    metodo = st.radio(
        "¿Cómo se actualiza el costo de un producto al comprarlo?", ["ULTIMO", "PROMEDIO"],
        index=0 if b.get("metodo_costo", "ULTIMO").upper() == "ULTIMO" else 1,
        format_func=lambda m: "📌 Último costo de compra" if m == "ULTIMO" else "⚖️ Costo promedio ponderado")
    if metodo == "ULTIMO":
        st.caption("Ejemplo: tenías 5 sensores a $3,50 y compras 10 a $4,00 → el costo pasa a **$4,00**. "
                   "Simple y refleja el precio actual del mercado.")
    else:
        st.caption("Ejemplo: tenías 5 sensores a $3,50 y compras 10 a $4,00 → el costo pasa a **$3,83** "
                   "(mezcla lo que tenías con lo nuevo).")
    prorr = st.toggle("Repartir flete y otros gastos en el costo de los productos",
                      U.es_verdadero(b.get("prorratear_gastos", "true")))
    st.caption("Ejemplo: compra de $70 con $7 de flete → cada producto cuesta 10% más. "
               "Así tu margen de ganancia es real." if prorr else
               "El flete se registra en la compra, pero no modifica el costo de los productos.")
    return {"metodo_costo": metodo, "prorratear_gastos": str(prorr).lower()}, None


def _form_seguridad(b: dict):
    st.info("Los administradores pueden **anular ventas y compras** y **cambiar esta configuración**. "
            "Si la lista queda vacía, todos los usuarios tienen esos permisos.")
    texto = st.text_area("Correos de los administradores (uno por línea)",
                         "\n".join(_admins(b.get("emails_administradores", ""))), height=100)
    lista = _admins(texto)
    error = None
    if lista:
        st.markdown(" ".join(f"`{escape(x)}`" for x in lista))
        if _email() and _email() not in lista:
            error = f"Incluye tu propio correo ({_email()}) para no perder el acceso."
    else:
        st.warning("Sin administradores definidos: cualquier usuario podrá anular documentos.")
    return {"emails_administradores": ", ".join(lista)}, error


FORMULARIOS = {"empresa": _form_empresa, "impuestos": _form_impuestos, "tasa": _form_tasa,
               "ventas": _form_ventas, "compras": _form_compras, "seguridad": _form_seguridad}


def _guardar(valores: dict) -> bool:
    if not U.es_admin(st.session_state._cfg, _email()):
        st.error("Solo un administrador puede modificar la configuración.")
        return False
    try:
        supabase.table("configuracion").upsert(
            [{"clave": k, "valor": str(v)} for k, v in valores.items()], on_conflict="clave").execute()
    except Exception as e:
        st.error(U.mensaje_error(e))
        return False
    st.session_state.pop("_sb_cache", None)   # el menú lateral toma el rol actualizado
    return True


def _mostrar(clave: str, valor) -> str:
    if clave in ("iva_por_defecto", "igtf_activo", "tasa_automatica", "permitir_venta_sin_stock", "prorratear_gastos"):
        return _si_no(valor)
    if clave == "metodo_costo":
        return "Último costo" if str(valor).upper() == "ULTIMO" else "Promedio ponderado"
    return str(valor) if str(valor).strip() else "—"


# =====================================================================
# VENTANAS
# =====================================================================
@st.dialog("🧭 Asistente de configuración", width="large")
def dialog_asistente():
    ss = st.session_state
    paso = ss.cfg_paso
    total = len(SECCIONES)
    _pasos(paso + 1, [f"{i + 1} · {s[2]}" for i, s in enumerate(SECCIONES)] + ["✔ Revisar"])

    if paso < total:
        clave, icono, titulo, desc = SECCIONES[paso]
        st.markdown(f"### {icono} Paso {paso + 1} de {total}: {titulo}")
        st.caption(desc)
        valores, error = FORMULARIOS[clave](ss.cfg_borrador)
        if error:
            st.caption(f"⚠️ {error}")
        st.divider()
        a, b = st.columns(2)
        if a.button("← Atrás", use_container_width=True, disabled=paso == 0):
            ss.cfg_borrador.update(valores)
            ss.cfg_paso -= 1
            st.rerun(scope="fragment")
        if b.button("Siguiente →", type="primary", use_container_width=True, disabled=bool(error)):
            ss.cfg_borrador.update(valores)
            ss.cfg_paso += 1
            st.rerun(scope="fragment")
        return

    # Último paso: revisar cambios
    st.markdown("### ✔ Revisa los cambios antes de guardar")
    actual = ss._cfg
    cambios = [{"Ajuste": ETIQUETAS.get(k, k), "Antes": _mostrar(k, actual.get(k, "")), "Ahora": _mostrar(k, v)}
               for k, v in ss.cfg_borrador.items() if k in ETIQUETAS and str(actual.get(k, "")) != str(v)]
    if cambios:
        st.dataframe(pd.DataFrame(cambios), hide_index=True, use_container_width=True)
    else:
        st.info("No hiciste cambios. Todo queda como estaba.")
    st.divider()
    a, b = st.columns(2)
    if a.button("← Atrás", use_container_width=True):
        ss.cfg_paso -= 1
        st.rerun(scope="fragment")
    if b.button("💾 Guardar configuración", type="primary", use_container_width=True, disabled=not cambios):
        datos = {k: v for k, v in ss.cfg_borrador.items() if k in ETIQUETAS}
        if _guardar(datos):
            st.session_state.cfg_msg = f"✅ Configuración guardada ({len(cambios)} cambio(s))."
            st.rerun()


@st.dialog("✏️ Editar configuración", width="large")
def dialog_seccion(clave: str):
    _, icono, titulo, desc = next(s for s in SECCIONES if s[0] == clave)
    st.markdown(f"### {icono} {titulo}")
    st.caption(desc)
    valores, error = FORMULARIOS[clave](dict(st.session_state._cfg))
    if error:
        st.caption(f"⚠️ {error}")
    st.divider()
    a, b = st.columns(2)
    if a.button("Cancelar", use_container_width=True):
        st.rerun()
    if b.button("💾 Guardar", type="primary", use_container_width=True, disabled=bool(error)):
        if _guardar(valores):
            st.session_state.cfg_msg = f"✅ {titulo}: cambios guardados."
            st.rerun()


@st.dialog("🧾 Vista previa del comprobante", width="large")
def dialog_preview():
    cfg = st.session_state._cfg
    aplica = U.es_verdadero(cfg.get("iva_por_defecto", "true"))
    iva_pct = float(cfg.get("iva_porcentaje", 16)) if aplica else 0
    tasa = float(U.tasa_vigente(supabase)[1] or 100)
    base = 25.0
    iva = round(base * iva_pct / 100, 2)
    venta = {
        "numero": f"{cfg.get('serie_documento', 'NE')}-00000001", "fecha": U.ahora_vzla().isoformat(),
        "fecha_tasa": str(U.hoy_vzla()), "tasa_bcv": tasa, "cliente_nombre": "CLIENTE DE EJEMPLO",
        "cliente_rif": "V-12345678", "usuario_email": _email(), "aplica_iva": aplica,
        "exento_usd": 0, "exento_bs": 0, "base_imponible_usd": base, "base_imponible_bs": round(base * tasa, 2),
        "iva_porcentaje": iva_pct, "iva_usd": iva, "iva_bs": round(round(base * tasa, 2) * iva_pct / 100, 2),
        "total_usd": base + iva, "total_bs": round((base + iva) * tasa, 2), "igtf_usd": 0, "igtf_bs": 0,
        "igtf_porcentaje": 0, "pagado_divisas_usd": 0, "total_pagar_usd": base + iva,
        "total_pagar_bs": round((base + iva) * tasa, 2), "vuelto_usd": 0, "vuelto_bs": 0, "estado": "EMITIDA",
    }
    detalle = [{"sku": "LED-0001", "descripcion": "Bombillo LED H4 (ejemplo)", "cantidad": 1,
                "precio_unitario_usd": base, "descuento_pct": 0, "subtotal_usd": base,
                "subtotal_bs": round(base * tasa, 2), "exento_iva": False}]
    pagos = [{"metodo": "Pago Móvil", "moneda": "VES", "monto": round((base + iva) * tasa, 2), "referencia": "1234"}]
    st.caption("Así verán tus clientes el comprobante con la configuración actual (datos de ejemplo).")
    components.html(generar_html(venta, detalle, pagos, cfg, con_boton=False), height=620, scrolling=True)


# =====================================================================
# PANTALLA PRINCIPAL
# =====================================================================
def _resumen(clave: str, cfg: dict) -> list[str]:
    if clave == "empresa":
        return [f"**{cfg['empresa_nombre']}**", f"RIF {cfg['empresa_rif']}",
                (cfg["empresa_direccion"] or "Sin dirección")[:60]]
    if clave == "impuestos":
        igtf = f"IGTF {cfg['igtf_porcentaje']}% sobre divisas" if U.es_verdadero(cfg["igtf_activo"]) else "IGTF desactivado"
        return [f"IVA {cfg['iva_porcentaje']}%",
                "Ventas nuevas: " + ("con IVA" if U.es_verdadero(cfg.get("iva_por_defecto", "true")) else "nota de entrega"),
                igtf]
    if clave == "tasa":
        return ["Automática al iniciar sesión: " + _si_no(cfg.get("tasa_automatica", "true")),
                f"Vigencia máxima: {cfg['tasa_dias_max']} días"]
    if clave == "ventas":
        return [f"Numeración {cfg['serie_documento']}-00000001", f"Descuento máximo {cfg['descuento_max_pct']}%",
                "Vender sin stock: " + _si_no(cfg["permitir_venta_sin_stock"])]
    if clave == "compras":
        return ["Costo: " + _mostrar("metodo_costo", cfg.get("metodo_costo", "ULTIMO")),
                "Flete en el costo: " + _si_no(cfg.get("prorratear_gastos", "true"))]
    lista = _admins(cfg.get("emails_administradores", ""))
    return [f"{len(lista)} administrador(es)" if lista else "⚠️ Todos los usuarios son administradores"] + lista[:2]


def _checklist(cfg: dict) -> list[tuple[str, bool]]:
    return [
        ("RIF de la empresa", cfg["empresa_rif"] not in ("", "J-00000000-0")),
        ("Dirección fiscal", cfg["empresa_direccion"].strip() not in ("", "Dirección fiscal")),
        ("Teléfono", bool(cfg["empresa_telefono"].strip())),
        ("Administradores definidos", bool(_admins(cfg.get("emails_administradores", "")))),
        ("Tasa BCV automática", U.es_verdadero(cfg.get("tasa_automatica", "true"))),
    ]


def render():
    ss = st.session_state
    st.markdown(CSS, unsafe_allow_html=True)
    cfg = U.obtener_config(supabase)
    ss._cfg = cfg
    admin = U.es_admin(cfg, _email())

    st.title("⚙️ Configuración")
    st.caption("Ajusta cómo funciona tu sistema. Si es la primera vez, usa el asistente: te guía paso a paso.")
    if ss.get("cfg_msg"):
        st.toast(ss.pop("cfg_msg"))
    if not admin:
        st.warning("🔒 Solo los administradores pueden modificar la configuración. Puedes consultarla.")

    items = _checklist(cfg)
    hechos = sum(ok for _, ok in items)
    with st.container(border=True):
        c1, c2 = st.columns([3, 1.3])
        with c1:
            st.markdown(f"**Estado de tu configuración: {hechos} de {len(items)} completos**")
            st.progress(hechos / len(items))
            st.markdown(" &nbsp; ".join(("✅ " if ok else "⬜ ") + n for n, ok in items))
        with c2:
            if st.button("🧭 Configurar paso a paso", type="primary", use_container_width=True, disabled=not admin):
                ss.cfg_paso = 0
                ss.cfg_borrador = {k: cfg.get(k, "") for k in ETIQUETAS}
                dialog_asistente()
            if st.button("🧾 Ver comprobante", use_container_width=True):
                dialog_preview()

    st.markdown("#### Secciones")
    cols = st.columns(3)
    for i, (clave, icono, titulo, desc) in enumerate(SECCIONES):
        with cols[i % 3].container(border=True):
            st.markdown(f"### {icono} {titulo}")
            st.caption(desc)
            for linea in _resumen(clave, cfg):
                st.markdown(f"<div style='font-size:.88rem; padding:.1rem 0'>{escape(linea)}</div>"
                            if not linea.startswith("**") else linea, unsafe_allow_html=True)
            if st.button("✏️ Editar", key=f"cfg_edit_{clave}", use_container_width=True, disabled=not admin):
                dialog_seccion(clave)
