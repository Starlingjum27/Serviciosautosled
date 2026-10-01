"""Comprobante de venta en HTML (ticket 80 mm o carta), listo para imprimir o descargar."""
from html import escape

from app.utils import fmt_num, fmt_usd, fmt_bs, fecha_hora_local, D


def cargar_venta(supabase, venta_id: int):
    venta = supabase.table("ventas").select("*").eq("id", venta_id).single().execute().data
    detalle = supabase.table("detalle_ventas").select("*").eq("venta_id", venta_id).order("id").execute().data or []
    pagos = supabase.table("pagos_venta").select("*").eq("venta_id", venta_id).order("id").execute().data or []
    return venta, detalle, pagos


def generar_html(venta: dict, detalle: list, pagos: list, cfg: dict, con_boton: bool = True) -> str:
    e = lambda s: escape(str(s or ""))
    tasa = D(venta["tasa_bcv"])

    filas = ""
    for d in detalle:
        desc = f" (-{fmt_num(d['descuento_pct'], 0)}%)" if D(d["descuento_pct"]) > 0 else ""
        exento = " (E)" if d.get("exento_iva") else ""
        filas += f"""
        <tr><td colspan="3" class="desc">{e(d['sku'])} · {e(d['descripcion'])}{exento}</td></tr>
        <tr><td>{d['cantidad']} x {fmt_usd(d['precio_unitario_usd'])}{desc}</td>
            <td class="r">{fmt_usd(d['subtotal_usd'])}</td>
            <td class="r">{fmt_bs(d['subtotal_bs'])}</td></tr>"""

    filas_pago = "".join(
        f"<tr><td>{e(p['metodo'])}{(' · Ref ' + e(p['referencia'])) if p.get('referencia') else ''}</td>"
        f"<td class='r'>{fmt_usd(p['monto']) if p['moneda'] == 'USD' else fmt_bs(p['monto'])}</td></tr>"
        for p in pagos
    )

    igtf = ""
    if D(venta["igtf_usd"]) > 0:
        igtf = f"""<tr><td>IGTF {fmt_num(venta['igtf_porcentaje'], 0)}% s/ {fmt_usd(venta['pagado_divisas_usd'])} en divisas</td>
                   <td class="r">{fmt_usd(venta['igtf_usd'])}</td><td class="r">{fmt_bs(venta['igtf_bs'])}</td></tr>"""

    vuelto = ""
    if D(venta["vuelto_usd"]) > 0 or D(venta["vuelto_bs"]) > 0:
        partes = []
        if D(venta["vuelto_usd"]) > 0:
            partes.append(fmt_usd(venta["vuelto_usd"]))
        if D(venta["vuelto_bs"]) > 0:
            partes.append(fmt_bs(venta["vuelto_bs"]))
        vuelto = f"<p class='c'><b>Vuelto:</b> {' + '.join(partes)}</p>"

    anulada = ""
    if venta.get("estado") == "ANULADA":
        anulada = f"<div class='anulada'>ANULADA<br><small>{e(venta.get('motivo_anulacion'))}</small></div>"

    boton = """<button class="noprint" onclick="window.print()">🖨️ Imprimir</button>""" if con_boton else ""

    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<title>{e(venta['numero'])}</title>
<style>
  body {{ font-family: 'Courier New', monospace; font-size: 12px; color:#000; background:#fff; margin:0; padding:12px; }}
  .ticket {{ max-width: 340px; margin: 0 auto; position: relative; }}
  h1 {{ font-size: 15px; margin: 0; text-align:center; }}
  .c {{ text-align:center; margin: 2px 0; }}
  .r {{ text-align:right; white-space:nowrap; }}
  table {{ width:100%; border-collapse: collapse; }}
  td {{ padding: 1px 0; vertical-align: top; }}
  .desc {{ font-weight:bold; padding-top:4px; }}
  hr {{ border: none; border-top: 1px dashed #000; margin: 6px 0; }}
  .tot td {{ font-weight: bold; font-size: 13px; }}
  .tasa {{ border:1px solid #000; padding:4px; text-align:center; margin:6px 0; }}
  .leyenda {{ font-size: 10px; text-align:center; margin-top:8px; }}
  .anulada {{ position:absolute; top:35%; left:0; right:0; text-align:center; color:#c00;
              font-size:34px; font-weight:bold; transform:rotate(-20deg); opacity:.55; border:4px solid #c00; }}
  button {{ display:block; margin:10px auto; padding:8px 18px; font-size:14px; cursor:pointer; }}
  @media print {{ .noprint {{ display:none; }} body {{ padding:0; }} }}
</style></head><body><div class="ticket">
  {anulada}
  <h1>{e(cfg.get('empresa_nombre'))}</h1>
  <p class="c">RIF: {e(cfg.get('empresa_rif'))}</p>
  <p class="c">{e(cfg.get('empresa_direccion'))}</p>
  <p class="c">{e(cfg.get('empresa_telefono'))}</p>
  <hr>
  <p><b>Documento N°:</b> {e(venta['numero'])}<br>
     <b>Fecha:</b> {fecha_hora_local(venta['fecha'])}<br>
     <b>Cliente:</b> {e(venta['cliente_nombre'])}<br>
     <b>RIF/C.I.:</b> {e(venta['cliente_rif'])}<br>
     <b>Atendido por:</b> {e(venta.get('usuario_email'))}</p>
  <hr>
  <table><tr><td><b>Descripción</b></td><td class="r"><b>USD</b></td><td class="r"><b>Bs</b></td></tr>{filas}</table>
  <hr>
  <table>
    <tr><td>Exento (E)</td><td class="r">{fmt_usd(venta['exento_usd'])}</td><td class="r">{fmt_bs(venta['exento_bs'])}</td></tr>
    <tr><td>Base imponible</td><td class="r">{fmt_usd(venta['base_imponible_usd'])}</td><td class="r">{fmt_bs(venta['base_imponible_bs'])}</td></tr>
    <tr><td>IVA {fmt_num(venta['iva_porcentaje'], 0)}%</td><td class="r">{fmt_usd(venta['iva_usd'])}</td><td class="r">{fmt_bs(venta['iva_bs'])}</td></tr>
    <tr class="tot"><td>TOTAL</td><td class="r">{fmt_usd(venta['total_usd'])}</td><td class="r">{fmt_bs(venta['total_bs'])}</td></tr>
    {igtf}
    <tr class="tot"><td>TOTAL A PAGAR</td><td class="r">{fmt_usd(venta['total_pagar_usd'])}</td><td class="r">{fmt_bs(venta['total_pagar_bs'])}</td></tr>
  </table>
  <div class="tasa">Tasa BCV aplicada: <b>Bs. {fmt_num(tasa, 4)}</b> por USD<br>
     Fecha valor: {e(str(venta['fecha_tasa']))}</div>
  <table><tr><td colspan="2"><b>Formas de pago</b></td></tr>{filas_pago}</table>
  {vuelto}
  <hr>
  <p class="leyenda">{e(cfg.get('leyenda_documento'))}<br>
     Los montos en USD son referenciales; el bolívar es la moneda de curso legal.</p>
  {boton}
</div></body></html>"""
