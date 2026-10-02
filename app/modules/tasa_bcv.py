import pandas as pd
import requests
import streamlit as st

from app.db import supabase
from app import utils as U

API_URL = "https://ve.dolarapi.com/v1/dolares/oficial"


def obtener_tasa_automatica():
    """Consulta una API pública que replica la tasa oficial BCV. Devuelve (tasa, fecha_actualizacion) o (None, None)."""
    try:
        r = requests.get(API_URL, timeout=10)
        if r.status_code == 200:
            data = r.json()
            tasa = float(data.get("promedio") or data.get("venta") or 0)
            return (tasa if tasa > 0 else None), data.get("fechaActualizacion")
    except Exception:
        pass
    return None, None


def auto_actualizar_tasa(forzar: bool = False) -> dict:
    """
    Se ejecuta al iniciar sesión. Registra la tasa del día si:
      - la actualización automática está activa (Configuración),
      - es día hábil (sábado y domingo se mantiene la del viernes),
      - aún no hay tasa con fecha de hoy (nunca sobrescribe una ya cargada),
      - el valor no varía más de 10% respecto a la vigente (protección contra datos erróneos).
    Devuelve {"estado": ok|al_dia|fin_semana|desactivada|revision|error, "mensaje": str}.
    """
    cfg = U.obtener_config(supabase)
    if not forzar and not U.es_verdadero(cfg.get("tasa_automatica", "true")):
        return {"estado": "desactivada", "mensaje": "La actualización automática está desactivada."}

    hoy = U.hoy_vzla()
    if hoy.weekday() >= 5:
        return {"estado": "fin_semana",
                "mensaje": "Fin de semana: se usa la tasa del último día hábil."}
    try:
        existe = supabase.table("tasas_bcv").select("tasa").eq("fecha", str(hoy)).limit(1).execute().data
    except Exception as e:
        return {"estado": "error", "mensaje": f"No se pudo leer la base de datos: {U.mensaje_error(e)}"}
    if existe and not forzar:
        return {"estado": "al_dia",
                "mensaje": f"Tasa de hoy ya registrada: Bs. {U.fmt_num(existe[0]['tasa'], 4)}"}

    tasa, _ = obtener_tasa_automatica()
    if not tasa:
        return {"estado": "error",
                "mensaje": "No se pudo consultar la tasa oficial. Regístrala manualmente en 💱 Tasa BCV."}

    _, vigente = U.tasa_vigente(supabase)
    if vigente and abs(U.D(tasa) - vigente) / vigente * 100 > 10:
        return {"estado": "revision",
                "mensaje": f"La tasa consultada (Bs. {U.fmt_num(tasa, 4)}) varía más de 10% respecto a la vigente. "
                           "Verifícala en bcv.org.ve y regístrala manualmente."}

    usuario = st.session_state.get("usuario")
    try:
        supabase.table("tasas_bcv").upsert(
            {"fecha": str(hoy), "tasa": round(tasa, 4), "fuente": "Automática · ve.dolarapi.com",
             "usuario_id": getattr(usuario, "id", None)},
            on_conflict="fecha",
        ).execute()
    except Exception as e:
        return {"estado": "error", "mensaje": f"No se pudo guardar la tasa: {U.mensaje_error(e)}"}
    return {"estado": "ok", "mensaje": f"Tasa BCV actualizada automáticamente: Bs. {U.fmt_num(tasa, 4)}"}


def render():
    st.title("💱 Tasa BCV")
    st.caption("Única tasa legal para convertir precios USD → Bs. Regístrala con su **fecha valor** "
               "(el viernes en la tarde el BCV publica la tasa con fecha valor del lunes).")

    estado = st.session_state.get("tasa_auto")
    if estado:
        icono = {"ok": "✅", "al_dia": "✅", "fin_semana": "📅", "desactivada": "⏸️"}.get(estado["estado"], "⚠️")
        c1, c2 = st.columns([4, 1])
        c1.caption(f"{icono} **Actualización automática:** {estado['mensaje']}")
        if c2.button("🔄 Reintentar", use_container_width=True, help="Consulta la API y registra la tasa de hoy"):
            with st.spinner("Consultando tasa oficial..."):
                st.session_state.tasa_auto = auto_actualizar_tasa(forzar=True)
            st.session_state.pop("_sb_cache", None)
            st.rerun()

    fecha_vig, tasa_vig = U.tasa_vigente(supabase)
    if tasa_vig:
        dias = (U.hoy_vzla() - fecha_vig).days
        msg = f"Tasa vigente: **Bs. {U.fmt_num(tasa_vig, 4)}** · fecha valor {fecha_vig:%d/%m/%Y}"
        (st.success if dias == 0 or U.hoy_vzla().weekday() >= 5 else st.warning)(
            msg + ("" if dias == 0 else f" ({dias} día(s) de antigüedad)"))
    else:
        st.error("No hay ninguna tasa registrada.")

    col1, col2 = st.columns([1, 2], gap="large")
    with col1:
        st.subheader("Consulta automática")
        if st.button("🔄 Consultar tasa oficial", use_container_width=True):
            with st.spinner("Consultando..."):
                tasa, actualizada = obtener_tasa_automatica()
            if tasa:
                st.session_state["tasa_sugerida"] = round(tasa, 4)
                st.session_state["tasa_input"] = round(tasa, 4)
                st.success(f"Encontrada: Bs. {U.fmt_num(tasa, 4)}")
                if actualizada:
                    st.caption(f"Actualizada en la fuente: {U.fecha_hora_local(actualizada)}")
            else:
                st.error("No se pudo consultar. Ingrésala manualmente desde bcv.org.ve.")
        st.caption("Fuente: ve.dolarapi.com (réplica). Verifica siempre contra bcv.org.ve.")

    with col2:
        st.subheader("Registrar / corregir")
        fecha = st.date_input("Fecha valor", U.hoy_vzla(), format="DD/MM/YYYY")
        st.session_state.setdefault("tasa_input", float(st.session_state.get("tasa_sugerida", 0.0)))
        tasa = st.number_input("Tasa BCV (Bs por USD)", min_value=0.0, format="%.4f", step=0.01, key="tasa_input")

        confirmar_salto = True
        if tasa_vig and tasa > 0:
            variacion = abs(U.D(tasa) - tasa_vig) / tasa_vig * 100
            if variacion > 10:
                st.warning(f"La tasa difiere {U.fmt_num(variacion, 1)}% de la vigente. Revisa que no haya un error de tipeo.")
                confirmar_salto = st.checkbox("Confirmo que el valor es correcto")

        if st.button("💾 Guardar tasa", type="primary", disabled=tasa <= 0 or not confirmar_salto):
            sugerida = st.session_state.get("tasa_sugerida")
            fuente = "API ve.dolarapi.com" if sugerida and abs(sugerida - tasa) < 0.00005 else "Manual"
            usuario = st.session_state.get("usuario")
            try:
                supabase.table("tasas_bcv").upsert(
                    {"fecha": str(fecha), "tasa": round(tasa, 4), "fuente": fuente,
                     "usuario_id": getattr(usuario, "id", None)},
                    on_conflict="fecha",
                ).execute()
            except Exception as e:
                st.error(f"Error al guardar: {U.mensaje_error(e)}")
            else:
                st.session_state.pop("tasa_sugerida", None)
                st.session_state.pop("_sb_cache", None)   # refresca la tasa del menú lateral
                st.toast(f"Tasa del {fecha:%d/%m/%Y} guardada ✅")
                st.rerun()

    st.divider()
    st.subheader("Histórico (últimas 60)")
    try:
        res = supabase.table("tasas_bcv").select("fecha, tasa, fuente, created_at").order("fecha", desc=True).limit(60).execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df["fecha"] = pd.to_datetime(df["fecha"])
            df["tasa"] = df["tasa"].astype(float)
            st.line_chart(df.set_index("fecha")["tasa"], height=220)
            df["fecha"] = df["fecha"].dt.strftime("%d/%m/%Y")
            df["created_at"] = df["created_at"].apply(U.fecha_hora_local)
            st.dataframe(df.rename(columns={"fecha": "Fecha valor", "tasa": "Tasa", "fuente": "Fuente",
                                            "created_at": "Registrada"}),
                         hide_index=True, use_container_width=True,
                         column_config={"Tasa": st.column_config.NumberColumn(format="%.4f")})
        else:
            st.info("No hay tasas registradas.")
    except Exception as e:
        st.error(f"Error cargando tasas: {U.mensaje_error(e)}")
