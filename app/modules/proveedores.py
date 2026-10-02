"""PROVEEDORES · registro, edición, activación y resumen de compras por proveedor."""
import pandas as pd
import streamlit as st

from app.db import supabase
from app import utils as U


def obtener_proveedores(solo_activos: bool = True) -> list[dict]:
    try:
        q = supabase.table("proveedores").select("*").order("nombre")
        if solo_activos:
            q = q.eq("activo", True)
        return q.execute().data or []
    except Exception:
        return []


def _resumen_compras() -> dict:
    """{proveedor_id: (n_compras, total_usd, ultima_fecha)} de compras registradas."""
    try:
        datos = (supabase.table("compras").select("proveedor_id, total_usd, fecha")
                 .eq("estado", "REGISTRADA").limit(5000).execute().data or [])
    except Exception:
        return {}
    res = {}
    for c in datos:
        n, tot, ult = res.get(c["proveedor_id"], (0, U.D(0), ""))
        res[c["proveedor_id"]] = (n + 1, tot + U.D(c["total_usd"]), max(ult, c["fecha"]))
    return res


@st.dialog("🏭 Proveedor", width="large")
def dialog_proveedor(prov: dict | None = None):
    """Crear (prov=None) o editar un proveedor."""
    editar = prov is not None
    prov = prov or {}
    st.markdown("### " + ("✏️ Editar proveedor" if editar else "➕ Nuevo proveedor"))

    tipo = st.radio("Tipo de proveedor", ["LOCAL", "IMPORTADO"], horizontal=True,
                    index=0 if prov.get("tipo", "LOCAL") == "LOCAL" else 1,
                    format_func=lambda x: "🇻🇪 Local (con RIF)" if x == "LOCAL" else "🌎 Importado / extranjero")

    rif = None
    if tipo == "LOCAL":
        actual = prov.get("rif", "")
        letra = actual[:1] if actual[:1] in "VEJGP" and actual else "J"
        c1, c2 = st.columns([1, 3])
        letra = c1.selectbox("Tipo", ["J", "V", "E", "G", "P"], index=["J", "V", "E", "G", "P"].index(letra))
        numero = c2.text_input("RIF *", value="".join(ch for ch in actual if ch.isdigit()),
                               placeholder="Ej: 123456789")
        rif = U.normalizar_rif(letra, numero) if numero else None
        if numero and not rif:
            st.caption("⚠️ El RIF debe tener entre 5 y 9 dígitos.")
        elif rif:
            st.caption(f"Se guardará como **{rif}**")
    else:
        rif = st.text_input("Identificación fiscal (Tax ID / EIN) *", value=prov.get("rif", ""),
                            placeholder="Ej: US-12-3456789").strip().upper() or None

    nombre = st.text_input("Nombre o razón social *", value=prov.get("nombre", ""))
    c1, c2 = st.columns(2)
    contacto = c1.text_input("Persona de contacto", value=prov.get("contacto") or "")
    telefono = c2.text_input("Teléfono / WhatsApp", value=prov.get("telefono") or "")
    c3, c4 = st.columns(2)
    email = c3.text_input("Correo", value=prov.get("email") or "")
    direccion = c4.text_input("Dirección", value=prov.get("direccion") or "")
    notas = st.text_area("Notas (condiciones, tiempos de entrega, cuentas bancarias…)", value=prov.get("notas") or "",
                         height=80)

    st.divider()
    a, b = st.columns(2)
    if a.button("Cancelar", use_container_width=True):
        st.rerun()
    if b.button("💾 Guardar", type="primary", use_container_width=True):
        if not rif or not nombre.strip():
            st.error("La identificación fiscal y el nombre son obligatorios.")
            return
        datos = {"rif": rif, "nombre": nombre.strip().upper(), "tipo": tipo, "contacto": contacto.strip() or None,
                 "telefono": telefono.strip() or None, "email": email.strip() or None,
                 "direccion": direccion.strip() or None, "notas": notas.strip() or None}
        try:
            if editar:
                supabase.table("proveedores").update(datos).eq("id", prov["id"]).execute()
            else:
                r = supabase.table("proveedores").insert(datos).execute()
                st.session_state["_prov_creado"] = r.data[0]["id"]
        except Exception as e:
            msg = U.mensaje_error(e)
            st.error("Ya existe un proveedor con esa identificación." if "duplicate" in msg.lower() else msg)
            return
        st.toast(f"Proveedor {datos['nombre']} guardado ✅")
        st.rerun()


@st.dialog("⚠️ Confirmar")
def dialog_estado(prov: dict, tiene_compras: bool):
    if prov["activo"]:
        st.markdown(f"¿Desactivar a **{prov['nombre']}**?")
        st.caption("No aparecerá al registrar compras, pero su historial se conserva.")
    else:
        st.markdown(f"¿Reactivar a **{prov['nombre']}**?")
    a, b = st.columns(2)
    if a.button("Cancelar", use_container_width=True):
        st.rerun()
    if b.button("Confirmar", type="primary", use_container_width=True):
        supabase.table("proveedores").update({"activo": not prov["activo"]}).eq("id", prov["id"]).execute()
        st.rerun()
    if not tiene_compras:
        st.divider()
        st.caption("Este proveedor no tiene compras, así que también puedes eliminarlo definitivamente.")
        if st.button("🗑️ Eliminar definitivamente", use_container_width=True):
            try:
                supabase.table("proveedores").delete().eq("id", prov["id"]).execute()
            except Exception as e:
                st.error(U.mensaje_error(e))
                return
            st.rerun()


def render():
    st.title("🏭 Proveedores")
    st.caption("Registra a quién le compras. Cada compra queda asociada a su proveedor.")

    c1, c2, c3 = st.columns([3, 2, 2])
    busqueda = c1.text_input("Buscar", placeholder="🔍 Nombre, RIF o contacto", label_visibility="collapsed")
    ver = c2.segmented_control("Ver", ["Activos", "Todos"], default="Activos", label_visibility="collapsed") or "Activos"
    if c3.button("➕ Nuevo proveedor", type="primary", use_container_width=True):
        dialog_proveedor()

    proveedores = obtener_proveedores(solo_activos=(ver == "Activos"))
    if busqueda:
        b = busqueda.lower()
        proveedores = [p for p in proveedores
                       if b in f"{p['nombre']} {p['rif']} {p.get('contacto') or ''}".lower()]
    if not proveedores:
        st.info("No hay proveedores. Presiona **➕ Nuevo proveedor** para registrar el primero.")
        return

    resumen = _resumen_compras()
    cols = st.columns(2)
    for i, p in enumerate(proveedores):
        n, total, ultima = resumen.get(p["id"], (0, U.D(0), ""))
        with cols[i % 2].container(border=True):
            a, b = st.columns([4, 2])
            a.markdown(f"**{p['nombre']}**" + ("" if p["activo"] else "  ·  🚫 Inactivo"))
            a.caption(f"{'🇻🇪' if p.get('tipo') == 'LOCAL' else '🌎'} {p['rif']}"
                      + (f" · {p['contacto']}" if p.get("contacto") else "")
                      + (f" · 📞 {p['telefono']}" if p.get("telefono") else ""))
            b.markdown(f"<div style='text-align:right'><b>{U.fmt_usd(total)}</b><br>"
                       f"<small>{n} compra(s)</small></div>", unsafe_allow_html=True)
            if ultima:
                st.caption(f"Última compra: {U.fecha_hora_local(ultima)}")
            e1, e2 = st.columns(2)
            if e1.button("✏️ Editar", key=f"prov_edit_{p['id']}", use_container_width=True):
                dialog_proveedor(p)
            if e2.button("🚫 Desactivar" if p["activo"] else "✅ Reactivar", key=f"prov_estado_{p['id']}",
                         use_container_width=True):
                dialog_estado(p, n > 0)

    if resumen:
        with st.expander("📊 Ranking de compras por proveedor"):
            nombres = {p["id"]: p["nombre"] for p in obtener_proveedores(solo_activos=False)}
            df = pd.DataFrame([{"Proveedor": nombres.get(pid, pid), "Compras": n, "Total USD": float(t)}
                               for pid, (n, t, _) in resumen.items()]).sort_values("Total USD", ascending=False)
            st.dataframe(df, hide_index=True, use_container_width=True,
                         column_config={"Total USD": st.column_config.NumberColumn(format="$ %.2f")})
