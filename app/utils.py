"""
Utilidades compartidas: fecha/hora de Venezuela, formatos, tasa BCV vigente,
configuración y el cálculo fiscal del POS (espejo exacto de registrar_venta en SQL).
"""
import re
from datetime import datetime, date, time
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Caracas")
CENT = Decimal("0.01")

CONFIG_DEFAULT = {
    "empresa_nombre": "SERVICIOS AUTOS LED",
    "empresa_rif": "J-00000000-0",
    "empresa_direccion": "",
    "empresa_telefono": "",
    "iva_porcentaje": "16",
    "iva_por_defecto": "true",
    "igtf_activo": "false",
    "igtf_porcentaje": "3",
    "serie_documento": "NE",
    "descuento_max_pct": "10",
    "permitir_venta_sin_stock": "false",
    "tasa_dias_max": "4",
    "emails_administradores": "",
    "leyenda_documento": "DOCUMENTO NO FISCAL.",
}


# ---------------------------------------------------------------- fechas
def ahora_vzla() -> datetime:
    """El servidor de Streamlit Cloud está en UTC; Venezuela es UTC-4."""
    return datetime.now(TZ)


def hoy_vzla() -> date:
    return ahora_vzla().date()


def rango_dia_iso(desde: date, hasta: date) -> tuple[str, str]:
    """Límites [desde 00:00, hasta 23:59:59] en hora de Venezuela, en ISO."""
    ini = datetime.combine(desde, time.min, TZ)
    fin = datetime.combine(hasta, time.max, TZ)
    return ini.isoformat(), fin.isoformat()


def fecha_hora_local(valor) -> str:
    if not valor:
        return ""
    try:
        dt = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
        return dt.astimezone(TZ).strftime("%d/%m/%Y %I:%M %p")
    except ValueError:
        return str(valor)


# ---------------------------------------------------------------- números
def D(x) -> Decimal:
    if x is None or x == "":
        return Decimal("0")
    return Decimal(str(x))


def r2(x) -> Decimal:
    """Redondeo comercial a 2 decimales (igual que round() de PostgreSQL)."""
    return D(x).quantize(CENT, rounding=ROUND_HALF_UP)


def fmt_num(x, dec: int = 2) -> str:
    """1234567.891 -> '1.234.567,89' (formato venezolano)."""
    s = f"{float(D(x)):,.{dec}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def fmt_bs(x) -> str:
    return f"Bs. {fmt_num(x)}"


def fmt_usd(x) -> str:
    return f"$ {fmt_num(x)}"


def es_verdadero(valor) -> bool:
    return str(valor).strip().lower() in ("true", "1", "si", "sí", "yes")


# ---------------------------------------------------------------- RIF
def normalizar_rif(tipo: str, numero: str) -> str | None:
    """('J','123456789') -> 'J-12345678-9' ; ('V','12345678') -> 'V-12345678'."""
    digitos = re.sub(r"\D", "", numero or "")
    if not 5 <= len(digitos) <= 9 or tipo not in "VEJGP":
        return None
    if len(digitos) == 9:
        return f"{tipo}-{digitos[:8]}-{digitos[8]}"
    return f"{tipo}-{digitos}"


# ---------------------------------------------------------------- BD
def mensaje_error(e: Exception) -> str:
    """Extrae el mensaje legible de los errores de PostgREST/Supabase."""
    msg = getattr(e, "message", None)
    if msg:
        return str(msg)
    if e.args and isinstance(e.args[0], dict):
        return e.args[0].get("message", str(e))
    return str(e)


def obtener_config(supabase) -> dict:
    cfg = dict(CONFIG_DEFAULT)
    try:
        res = supabase.table("configuracion").select("clave, valor").execute()
        for fila in res.data or []:
            cfg[fila["clave"]] = fila["valor"]
    except Exception:
        pass
    return cfg


def tasa_vigente(supabase):
    """Devuelve (fecha_tasa: date, tasa: Decimal) o (None, None)."""
    try:
        res = supabase.rpc("tasa_vigente", {}).execute()
        if res.data:
            fila = res.data[0]
            return date.fromisoformat(str(fila["fecha_tasa"])[:10]), D(fila["tasa"])
    except Exception:
        pass
    return None, None


def es_admin(cfg: dict, email: str | None) -> bool:
    lista = [x.strip().lower() for x in cfg.get("emails_administradores", "").split(",") if x.strip()]
    return not lista or (email or "").lower() in lista


# ---------------------------------------------------------------- cálculo fiscal
def calcular_totales(items: list[dict], pagos: list[dict], tasa, cfg: dict) -> dict:
    """
    items: [{precio_usd, cantidad, descuento_pct, exento_iva}]
    pagos: [{moneda: 'USD'|'VES', monto}]
    Reglas:
      * IVA sobre el monto en Bs (base_bs * 16%).
      * IGTF (si la empresa es Contribuyente Especial) SOLO sobre la porción pagada en divisas.
        Lo entregado en divisas cubre "porción + IGTF de esa porción".
    """
    tasa = D(tasa)
    iva_pct = D(cfg.get("iva_porcentaje", "16"))
    igtf_pct = D(cfg.get("igtf_porcentaje", "3")) if es_verdadero(cfg.get("igtf_activo")) else Decimal("0")

    exento_usd = Decimal("0")
    base_usd = Decimal("0")
    for it in items:
        sub = r2(D(it["precio_usd"]) * D(it["cantidad"]) * (1 - D(it.get("descuento_pct", 0)) / 100))
        if it.get("exento_iva"):
            exento_usd += sub
        else:
            base_usd += sub

    iva_usd = r2(base_usd * iva_pct / 100)
    total_usd = exento_usd + base_usd + iva_usd
    exento_bs = r2(exento_usd * tasa)
    base_bs = r2(base_usd * tasa)
    iva_bs = r2(base_bs * iva_pct / 100)
    total_bs = exento_bs + base_bs + iva_bs

    usd_ent = sum((D(p["monto"]) for p in pagos if p["moneda"] == "USD"), Decimal("0"))
    bs_ent = sum((D(p["monto"]) for p in pagos if p["moneda"] == "VES"), Decimal("0"))

    divisas = min(r2(usd_ent / (1 + igtf_pct / 100)), total_usd)
    igtf_usd = r2(divisas * igtf_pct / 100)
    igtf_bs = r2(igtf_usd * tasa)
    bs_req = Decimal("0") if divisas >= total_usd else max(total_bs - r2(divisas * tasa), Decimal("0"))

    falta_bs = max(bs_req - bs_ent, Decimal("0"))
    completo = total_usd > 0 and (bs_ent + Decimal("0.009")) >= bs_req

    return {
        "exento_usd": exento_usd, "base_usd": base_usd, "iva_usd": iva_usd, "total_usd": total_usd,
        "exento_bs": exento_bs, "base_bs": base_bs, "iva_bs": iva_bs, "total_bs": total_bs,
        "iva_pct": iva_pct, "igtf_pct": igtf_pct,
        "usd_entregado": usd_ent, "bs_entregado": bs_ent,
        "divisas_aplicadas": divisas, "igtf_usd": igtf_usd, "igtf_bs": igtf_bs,
        "bs_requerido": bs_req, "falta_bs": falta_bs, "completo": completo,
        "total_pagar_usd": total_usd + igtf_usd, "total_pagar_bs": total_bs + igtf_bs,
        "vuelto_usd": max(usd_ent - divisas - igtf_usd, Decimal("0")),
        "vuelto_bs": max(bs_ent - bs_req, Decimal("0")),
        # Si pagara TODO en divisas:
        "total_todo_divisas_usd": total_usd + r2(total_usd * igtf_pct / 100),
    }


def monto_para_completar(items, pagos, tasa, cfg, moneda: str) -> Decimal:
    """Monto exacto que falta, en la moneda indicada (incluye IGTF si es USD)."""
    t = calcular_totales(items, pagos, tasa, cfg)
    if t["completo"]:
        return Decimal("0")
    if moneda == "VES":
        return t["falta_bs"]
    # USD: estimar y ajustar centavo a centavo hasta cubrir (por redondeos)
    porcion = (t["falta_bs"] / D(tasa)).quantize(CENT, rounding=ROUND_CEILING)
    x = (porcion * (1 + t["igtf_pct"] / 100)).quantize(CENT, rounding=ROUND_CEILING)
    def cubre(monto):
        return calcular_totales(items, pagos + [{"moneda": "USD", "monto": monto}], tasa, cfg)["completo"]

    for _ in range(20):
        if cubre(x):
            break
        x += CENT
    while x > CENT and cubre(x - CENT):
        x -= CENT
    return x
