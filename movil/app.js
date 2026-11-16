/* =====================================================================
   Autos LED · app móvil
   Usa la MISMA base de datos y las MISMAS funciones del sistema principal:
   - registrar_venta (stock, kardex, IVA en Bs, IGTF) → todo se calcula y valida en el servidor
   - tasa_vigente, configuracion, productos, ventas, clientes
   Pantallas: Inicio · Vender · Productos · Ventas
   ===================================================================== */
"use strict";
(() => {
  const CFG = window.APP_CONFIG || {};
  const app = document.getElementById("app");
  const sheetEl = document.getElementById("sheet");
  const toastEl = document.getElementById("toast");
  const $ = (s, el = document) => el.querySelector(s);

  if (!CFG.SUPABASE_URL || CFG.SUPABASE_URL.includes("TU-PROYECTO") || !CFG.SUPABASE_ANON_KEY ||
      CFG.SUPABASE_ANON_KEY.includes("PEGA_AQUI")) {
    app.innerHTML = `<div class="login"><h1>Falta un paso</h1>
      <p>Abre el archivo <b>config.js</b> y escribe la URL y la clave pública (anon key) de tu proyecto de Supabase.</p></div>`;
    return;
  }
  const sb = window.supabase.createClient(CFG.SUPABASE_URL, CFG.SUPABASE_ANON_KEY, {
    auth: { persistSession: true, autoRefreshToken: true },
  });

  // Mismos nombres que usa el sistema principal (así cuadran los cierres de caja)
  const METODOS = [
    { id: "Pago Móvil", moneda: "VES", ref: true, ico: "📱" },
    { id: "Punto de Venta", moneda: "VES", ref: true, ico: "💳" },
    { id: "Efectivo Bs", moneda: "VES", ref: false, ico: "💵" },
    { id: "Transferencia Bs", moneda: "VES", ref: true, ico: "🏦" },
    { id: "Efectivo USD", moneda: "USD", ref: false, ico: "💲" },
    { id: "Zelle", moneda: "USD", ref: true, ico: "🇺🇸" },
  ];

  const S = {
    user: null, cfg: {}, tasa: 0, fechaTasa: null, productos: [],
    tab: "inicio", q: "", cart: [], pagos: [], aplicaIva: true,
    cliente: { modo: "final", tipo: "V", numero: "", nombre: "", telefono: "" },
    metodo: "Pago Móvil", pagoRef: "", pagoMonto: "", verParcial: false,
    hoja: null, cobroPaso: 1, prodSel: null, ultima: null, ventaDia: null,
    fechaVentas: null, ventaKey: uuid(), enviando: false, filtroProd: "todos", editPrecio: null, precioEdit: "",
  };
  let instalarEvt = null;
  let camara = null;

  // ------------------------------------------------------------------ utilidades
  function uuid() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
    });
  }
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const esV = (v) => ["true", "1", "si", "sí", "yes"].includes(String(v ?? "").trim().toLowerCase());
  const norm = (s) => String(s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");

  /** Redondeo comercial a 2 decimales, igual que round() de PostgreSQL. */
  function r2(n) {
    n = Number(Number(n || 0).toFixed(10));
    const a = Math.abs(n);
    if (a < 0.0001) return 0;
    return Math.sign(n) * Number(Math.round(Number(a + "e2")) + "e-2");
  }
  const ceil2 = (n) => Math.ceil(Number((Number(n) * 100).toFixed(6))) / 100;
  const f2 = new Intl.NumberFormat("es-VE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const f4 = new Intl.NumberFormat("es-VE", { minimumFractionDigits: 4, maximumFractionDigits: 4 });
  const usd = (n) => "$ " + f2.format(n || 0);
  const bs = (n) => "Bs. " + f2.format(n || 0);

  const TZ = "America/Caracas";
  const hoy = () => new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(new Date());
  const esFinDeSemana = () => ["Sat", "Sun"].includes(new Date().toLocaleDateString("en-US", { timeZone: TZ, weekday: "short" }));
  const dm = (iso) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}` : "—");
  const dmy = (iso) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}` : "—");
  const fechaHora = (iso) => new Date(iso).toLocaleString("es-VE", { timeZone: TZ, day: "2-digit", month: "2-digit", year: "numeric", hour: "numeric", minute: "2-digit" });
  const hora = (iso) => new Date(iso).toLocaleTimeString("es-VE", { timeZone: TZ, hour: "numeric", minute: "2-digit" });
  const diasTasa = () => (S.fechaTasa ? Math.round((Date.parse(hoy()) - Date.parse(S.fechaTasa)) / 86400000) : 99);
  const tasaVieja = () => !S.tasa || (diasTasa() > 0 && !esFinDeSemana());
  const tasaBloqueada = () => !S.tasa || diasTasa() > Number(S.cfg.tasa_dias_max || 4);
  const permiteSinStock = () => esV(S.cfg.permitir_venta_sin_stock);
  const puedeEscanear = () => "BarcodeDetector" in window && !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);

  function parseMonto(s) {
    s = String(s || "").replace(/\s/g, "");
    if (s.includes(",") && s.includes(".")) s = s.replace(/\./g, "").replace(",", ".");
    else s = s.replace(",", ".");
    const n = Number(s);
    return Number.isFinite(n) ? r2(n) : 0;
  }
  function normalizarRif(tipo, numero) {
    const d = String(numero || "").replace(/\D/g, "");
    if (d.length < 5 || d.length > 9) return null;
    return d.length === 9 ? `${tipo}-${d.slice(0, 8)}-${d[8]}` : `${tipo}-${d}`;
  }
  let toastTimer;
  function toast(msg, mal = false) {
    toastEl.textContent = msg;
    toastEl.className = "ver" + (mal ? " mal" : "");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (toastEl.className = ""), mal ? 4200 : 1800);
  }
  const nombreUsuario = () => {
    const m = (S.user && S.user.user_metadata) || {};
    return m.nombre || m.full_name || (S.user ? S.user.email : "");
  };

  // ------------------------------------------------------------------ cálculo (espejo de registrar_venta)
  function calc(pagos = S.pagos) {
    const tasa = S.tasa;
    const ivaPct = S.aplicaIva ? Number(S.cfg.iva_porcentaje || 16) : 0;
    const igtfPct = esV(S.cfg.igtf_activo) ? Number(S.cfg.igtf_porcentaje || 3) : 0;
    let ex = 0, base = 0;
    for (const it of S.cart) {
      const sub = r2(precioCobrado(it) * it.cantidad);
      if (it.exento) ex = r2(ex + sub); else base = r2(base + sub);
    }
    const ivaUsd = r2(base * ivaPct / 100);
    const totalUsd = r2(ex + base + ivaUsd);
    const exBs = r2(ex * tasa), baseBs = r2(base * tasa);
    const ivaBs = r2(baseBs * ivaPct / 100);
    const totalBs = r2(exBs + baseBs + ivaBs);
    const usdEnt = r2(pagos.filter((p) => p.moneda === "USD").reduce((a, p) => a + p.monto, 0));
    const bsEnt = r2(pagos.filter((p) => p.moneda === "VES").reduce((a, p) => a + p.monto, 0));
    const divisas = Math.min(r2(usdEnt / (1 + igtfPct / 100)), totalUsd);
    const igtfUsd = r2(divisas * igtfPct / 100);
    const bsReq = divisas >= totalUsd ? 0 : Math.max(r2(totalBs - r2(divisas * tasa)), 0);
    const faltaBs = Math.max(r2(bsReq - bsEnt), 0);
    return {
      ex, base, ivaPct, igtfPct, ivaUsd, totalUsd, exBs, baseBs, ivaBs, totalBs, usdEnt, bsEnt, divisas, igtfUsd,
      igtfBs: r2(igtfUsd * tasa), bsReq, faltaBs,
      completo: totalUsd > 0 && bsEnt + 0.009 >= bsReq,
      vueltoUsd: Math.max(r2(usdEnt - divisas - igtfUsd), 0), vueltoBs: Math.max(r2(bsEnt - bsReq), 0),
      todoDivisas: r2(totalUsd + r2(totalUsd * igtfPct / 100)),
    };
  }
  function montoExacto(moneda) {
    const t = calc();
    if (t.completo) return 0;
    if (moneda === "VES") return t.faltaBs;
    const cubre = (x) => calc(S.pagos.concat([{ moneda: "USD", monto: x }])).completo;
    let x = ceil2(ceil2(t.faltaBs / S.tasa) * (1 + t.igtfPct / 100));
    for (let i = 0; i < 20 && !cubre(x); i++) x = r2(x + 0.01);
    while (x > 0.01 && cubre(r2(x - 0.01))) x = r2(x - 0.01);
    return x;
  }

  // ------------------------------------------------------------------ datos
  async function cargarBase() {
    const [cfgR, tasaR] = await Promise.all([sb.from("configuracion").select("clave, valor"), sb.rpc("tasa_vigente")]);
    if (cfgR.error) throw cfgR.error;
    S.cfg = Object.fromEntries((cfgR.data || []).map((r) => [r.clave, r.valor]));
    const t = (tasaR.data || [])[0];
    S.tasa = t ? Number(t.tasa) : 0;
    S.fechaTasa = t ? String(t.fecha_tasa).slice(0, 10) : null;
    if (!S.cart.length) S.aplicaIva = esV(S.cfg.iva_por_defecto ?? "true");
    await cargarProductos();
  }
  async function cargarProductos() {
    let todos = [], desde = 0;
    for (;;) {
      const { data, error } = await sb.from("productos")
        .select("id, sku, nombre, marca, precio_usd, costo_usd, stock_actual, stock_minimo, exento_iva, activo, tipo")
        .eq("activo", true).order("nombre").range(desde, desde + 999);
      if (error) throw error;
      todos = todos.concat(data || []);
      if (!data || data.length < 1000) break;
      desde += 1000;
    }
    S.productos = todos.map((p) => ({
      id: p.id, sku: p.sku, nombre: p.nombre, marca: p.marca || "", precio: Number(p.precio_usd) || 0, costo: Number(p.costo_usd) || 0,
      stock: Number(p.stock_actual) || 0, minimo: Number(p.stock_minimo) || 0, exento: !!p.exento_iva,
      servicio: p.tipo === "SERVICIO",
      _b: norm(`${p.sku} ${p.nombre} ${p.marca || ""}`),
    }));
  }
  function buscar(q, limite = 40) {
    const palabras = norm(q).split(/\s+/).filter(Boolean);
    const res = palabras.length ? S.productos.filter((p) => palabras.every((w) => p._b.includes(w))) : S.productos;
    return res.slice(0, limite);
  }
  const prod = (id) => S.productos.find((p) => p.id === id);
  const enVenta = (id) => (S.cart.find((i) => i.id === id) || {}).cantidad || 0;
  // Los servicios (mano de obra) no llevan inventario: no cuentan para stock, agotados ni reposición
  const inventario = () => S.productos.filter((p) => !p.servicio);
  function chipStock(p) {
    if (p.servicio) return `<span class="stock ok">Servicio</span>`;
    if (p.stock <= 0) return `<span class="stock cero">Agotado</span>`;
    if (p.stock <= p.minimo) return `<span class="stock bajo">Quedan ${p.stock}</span>`;
    return `<span class="stock ok">${p.stock} disp.</span>`;
  }

  // ------------------------------------------------------------------ íconos
  const ICO = {
    inicio: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/></svg>`,
    vender: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="20" r="1.5"/><circle cx="18" cy="20" r="1.5"/><path d="M2 3h3l2.6 12.4a1 1 0 0 0 1 .8h9.7a1 1 0 0 0 1-.8L21 7H6"/></svg>`,
    productos: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 8l-9-5-9 5 9 5 9-5z"/><path d="M3 8v8l9 5 9-5V8"/><path d="M12 13v8"/></svg>`,
    ventas: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2h12v20l-3-2-3 2-3-2-3 2z"/><path d="M9 7h6M9 11h6M9 15h4"/></svg>`,
    scan: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3"/><path d="M7 9v6M10 9v6M13 9v6M16 9v6"/></svg>`,
  };
  const TABS = [["inicio", "Inicio"], ["vender", "Vender"], ["productos", "Productos"], ["ventas", "Ventas"]];

  // ------------------------------------------------------------------ estructura
  function shell() {
    app.innerHTML = `
      <header class="top">
        <div class="marca"><img class="logo-top" src="icons/logo.png" alt="Servicios Autos LED"></div>
        <div class="tasa ${tasaVieja() ? "vieja" : ""}"><span class="num">Bs. ${f4.format(S.tasa)}</span><small>BCV ${dm(S.fechaTasa)}</small></div>
      </header>
      <main id="main"></main>
      <div id="totalbar"></div>
      <nav class="tabs" aria-label="Secciones">
        ${TABS.map(([id, txt]) => `<button data-a="tab" data-v="${id}" id="tab-${id}">${ICO[id]}${txt}</button>`).join("")}
      </nav>`;
  }
  function ir(tab) {
    S.tab = tab;
    TABS.forEach(([id]) => $("#tab-" + id) && $("#tab-" + id).classList.toggle("activo", id === tab));
    window.scrollTo(0, 0);
    ({ inicio: pantallaInicio, vender: pantallaVender, productos: pantallaProductos, ventas: pantallaVentas })[tab]();
    renderTotalbar();
  }
  function renderTotalbar() {
    const el = $("#totalbar");
    if (!el) return;
    if (!S.cart.length || !["vender", "productos"].includes(S.tab)) { el.innerHTML = ""; return; }
    const t = calc([]);
    const unidades = S.cart.reduce((a, i) => a + i.cantidad, 0);
    el.innerHTML = `<div class="totalbar">
      <div class="info"><div class="bs num">${bs(t.totalBs)}</div>
        <div class="det">${unidades} artículo${unidades === 1 ? "" : "s"}, ${usd(t.totalUsd)} ${S.aplicaIva ? "con IVA" : "sin IVA"}</div></div>
      <button class="btn btn-haz" data-a="verVenta">Ver venta</button></div>`;
  }

  // ------------------------------------------------------------------ login
  function pantallaLogin(msg = "") {
    app.innerHTML = `<form class="login" id="fLogin" novalidate>
      <img class="logo-login" src="icons/logo.png" alt="Servicios Autos LED">
      <h1>Bienvenido</h1>
      <p>Entra con el mismo correo y contraseña del sistema.</p>
      <label class="campo"><span>Correo</span><input name="email" type="email" inputmode="email" autocomplete="username" required></label>
      <label class="campo"><span>Contraseña</span><input name="clave" type="password" autocomplete="current-password" required></label>
      ${msg ? `<div class="error">${esc(msg)}</div>` : ""}
      <button class="btn btn-haz btn-ancho" type="submit" id="bEntrar">Entrar</button>
    </form>`;
    $("#fLogin").addEventListener("submit", async (e) => {
      e.preventDefault();
      const f = new FormData(e.target);
      const b = $("#bEntrar"); b.disabled = true; b.textContent = "Entrando…";
      const { data, error } = await sb.auth.signInWithPassword({ email: String(f.get("email")).trim(), password: String(f.get("clave")) });
      if (error) return pantallaLogin("Correo o contraseña incorrectos.");
      S.user = data.user;
      iniciar();
    });
  }
  async function iniciar() {
    try {
      await cargarBase();
    } catch (e) {
      app.innerHTML = `<div class="login"><h1>No se pudo cargar</h1><p>${esc(e.message || e)}</p>
        <button class="btn btn-haz btn-ancho" data-a="recargar">Reintentar</button></div>`;
      return;
    }
    shell();
    ir(S.tab);
  }

  // ------------------------------------------------------------------ INICIO
  function avisoTasa() {
    if (!S.tasa) return `<div class="aviso">No hay tasa BCV registrada. Regístrala en el sistema principal para poder vender.</div>`;
    if (tasaBloqueada()) return `<div class="aviso">La tasa BCV es del ${dmy(S.fechaTasa)} y está vencida. Actualízala en el sistema principal para poder vender.</div>`;
    if (tasaVieja()) return `<div class="aviso">La tasa es del ${dmy(S.fechaTasa)}. Verifica que la de hoy esté registrada en el sistema principal.</div>`;
    return "";
  }
  function bloqueInstalar() {
    const instalada = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone;
    if (instalada) return "";
    if (instalarEvt) return `<div class="instalar"><b>Instala la app en este teléfono.</b> Tendrás su ícono en la pantalla de inicio y abrirá sin el navegador.
      <div style="margin-top:10px"><button class="btn btn-haz btn-ancho" data-a="instalar">Instalar app</button></div></div>`;
    if (/iphone|ipad|ipod/i.test(navigator.userAgent))
      return `<div class="instalar"><b>Instálala en tu iPhone:</b> en Safari toca el botón Compartir y elige “Agregar a pantalla de inicio”.</div>`;
    return `<div class="instalar"><b>Instálala en tu teléfono:</b> abre el menú ⋮ del navegador y elige “Instalar app” o “Agregar a pantalla de inicio”.</div>`;
  }
  function saludo() {
    const h = Number(new Date().toLocaleString("en-US", { timeZone: TZ, hour: "numeric", hour12: false }));
    const nombre = nombreUsuario().split("@")[0].split(/[ ._]/)[0];
    const n = nombre ? nombre.charAt(0).toUpperCase() + nombre.slice(1) : "";
    return `${h < 12 ? "Buenos días" : h < 19 ? "Buenas tardes" : "Buenas noches"}${n ? ", " + esc(n) : ""}`;
  }
  // ------------------------------------------------------------------ INICIO (mismo panel que el Dashboard web)
  const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
  const diaLocal = (iso) => new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(new Date(iso));
  function chipVariacion(actual, anterior) {
    if (!(anterior > 0)) return actual > 0 ? `<span class="chip ch-up">▲ nuevo</span>` : `<span class="chip ch-flat">sin referencia</span>`;
    const pct = (actual - anterior) / anterior * 100;
    if (Math.abs(pct) < 0.05) return `<span class="chip ch-flat">= igual</span>`;
    return `<span class="chip ${pct > 0 ? "ch-up" : "ch-down"}">${pct > 0 ? "▲" : "▼"} ${f2.format(Math.abs(pct))}%</span>`;
  }
  function kpi(ico, etiqueta, valor, sub, chip, color) {
    return `<div class="kpi" style="--acc:${color}">
      <div class="kpi-top"><span class="kpi-ico">${ico}</span>${chip || ""}</div>
      <div class="kpi-et">${etiqueta}</div><div class="kpi-val num">${valor}</div><div class="kpi-sub">${sub}</div></div>`;
  }
  async function datosDashboard() {
    const h = hoy();
    const mesIni = h.slice(0, 8) + "01";
    const d30 = new Date(Date.parse(h + "T12:00:00Z") - 29 * 86400000).toISOString().slice(0, 10);
    const desde = d30 < mesIni ? d30 : mesIni;
    const [vR, tR, cR] = await Promise.all([
      sb.from("ventas").select("id, numero, fecha, cliente_nombre, total_usd, total_bs, total_pagar_usd, total_pagar_bs, tasa_bcv, estado")
        .gte("fecha", `${desde}T00:00:00-04:00`).order("fecha", { ascending: false }).limit(5000),
      sb.from("tasas_bcv").select("fecha, tasa").order("fecha", { ascending: false }).limit(2),
      sb.from("compras").select("total_usd").eq("estado", "REGISTRADA").gte("fecha", `${mesIni}T00:00:00-04:00`),
    ]);
    if (vR.error) throw vR.error;
    const ventas = (vR.data || []).map((v) => ({ ...v, dia: diaLocal(v.fecha) }));
    const emit = ventas.filter((v) => v.estado === "EMITIDA");
    const ids = emit.filter((v) => v.dia >= mesIni).map((v) => v.id);
    const lotes = async (tabla, cols) => {
      let out = [];
      for (let i = 0; i < ids.length; i += 150) {
        const { data } = await sb.from(tabla).select(cols).in("venta_id", ids.slice(i, i + 150));
        out = out.concat(data || []);
      }
      return out;
    };
    const [detalle, pagos] = await Promise.all([
      lotes("detalle_ventas", "venta_id, descripcion, cantidad, subtotal_usd, costo_unitario_usd"),
      lotes("pagos_venta", "venta_id, metodo, moneda, monto"),
    ]);
    return { h, mesIni, ventas, emit, detalle, pagos, compras: cR.data || [], tasas: tR.data || [] };
  }
  function heroInicio() {
    const fecha = new Date().toLocaleDateString("es-VE", { timeZone: TZ, weekday: "long", day: "numeric", month: "long", year: "numeric" });
    const estado = !S.tasa ? ["#ff4d5e", "Sin tasa registrada"] : tasaVieja() ? ["#ffb020", "Verifica la tasa de hoy"] : ["#2fd47a", "Al día"];
    return `<section class="hero">
      <div class="hero-izq">
        <div class="hero-sal">${saludo()} 👋</div>
        <img class="hero-logo" src="icons/logo.png" alt="Servicios Autos LED">
        <div class="hero-fecha">${fecha.charAt(0).toUpperCase() + fecha.slice(1)}. Panel de control del negocio</div>
      </div>
      <div class="hero-tasa">
        <div class="t1">Tasa oficial BCV</div>
        <div class="t2 num">Bs. ${f4.format(S.tasa)}</div>
        <div class="t3">Fecha valor ${dmy(S.fechaTasa)} <span id="chipTasa"></span></div>
        <div class="t3"><span class="punto" style="background:${estado[0]};box-shadow:0 0 8px ${estado[0]}"></span>${estado[1]}</div>
      </div>
    </section>`;
  }
  function graficoVentas(d) {
    const dias = [];
    for (let i = 29; i >= 0; i--) dias.push(new Date(Date.parse(d.h + "T12:00:00Z") - i * 86400000).toISOString().slice(0, 10));
    const tot = Object.fromEntries(dias.map((x) => [x, 0]));
    d.emit.forEach((v) => { if (v.dia in tot) tot[v.dia] += Number(v.total_usd); });
    const vals = dias.map((x) => tot[x]);
    const max = Math.max(...vals);
    if (!(max > 0)) return `<div class="vacio-mini">Aún no hay ventas en los últimos 30 días.</div>`;
    const W = 300, H = 110, paso = W / 30;
    const barras = vals.map((v, i) => {
      const alto = v > 0 ? Math.max(3, (v / max) * (H - 14)) : 2;
      return `<rect x="${(i * paso + 1.2).toFixed(1)}" y="${(H - alto).toFixed(1)}" width="${(paso - 2.4).toFixed(1)}" height="${alto.toFixed(1)}" rx="2"
        fill="${i === 29 ? "#60c5e3" : v > 0 ? "rgba(96,197,227,.55)" : "rgba(147,163,196,.18)"}"><title>${dm(dias[i])}: ${usd(v)}</title></rect>`;
    }).join("");
    return `<svg class="svg-ventas" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Ventas diarias de los últimos 30 días">${barras}</svg>
      <div class="ejes"><span>${dm(dias[0])}</span><span>${dm(dias[15])}</span><span>Hoy</span></div>
      <div class="kpi-sub" style="margin-top:6px">Mejor día: ${usd(max)}. Total 30 días: ${usd(vals.reduce((a, b) => a + b, 0))}</div>`;
  }
  function barrasLista(items, vacio) {
    if (!items.length) return `<div class="vacio-mini">${vacio}</div>`;
    const max = Math.max(...items.map((x) => x.valor)) || 1;
    return items.map((x, i) => `<div class="barra-fila">
      <div class="barra-cab"><span>${esc(x.nombre)}</span><b class="num">${x.texto}</b></div>
      <div class="barra-pista"><div style="width:${(x.valor / max * 100).toFixed(1)}%;background:${PALETA[i % PALETA.length]}"></div></div>
      ${x.sub ? `<div class="barra-sub">${x.sub}</div>` : ""}</div>`).join("");
  }
  const PALETA = ["#60c5e3", "#7c3aed", "#2fd47a", "#ffb020", "#ff4d5e", "#ec4899", "#14b8a6"];
  function panel(titulo, sub, cuerpo) {
    return `<section class="panel"><div class="panel-t">${titulo}</div><div class="panel-s">${sub}</div>${cuerpo}</section>`;
  }
  function htmlDashboard(d) {
    const ayer = new Date(Date.parse(d.h + "T12:00:00Z") - 86400000).toISOString().slice(0, 10);
    const suma = (arr, k) => arr.reduce((a, v) => a + Number(v[k] || 0), 0);
    const vHoy = d.emit.filter((v) => v.dia === d.h), vAyer = d.emit.filter((v) => v.dia === ayer);
    const vMes = d.emit.filter((v) => v.dia >= d.mesIni);
    const neto = suma(d.detalle, "subtotal_usd");
    const costo = d.detalle.reduce((a, x) => a + Number(x.cantidad) * Number(x.costo_unitario_usd || 0), 0);
    const util = neto - costo, margen = neto > 0 ? util / neto * 100 : 0;
    const usdMes = suma(vMes, "total_usd");
    const valCosto = inventario().reduce((a, p) => a + Math.max(p.stock, 0) * p.costo, 0);
    const valVenta = inventario().reduce((a, p) => a + Math.max(p.stock, 0) * p.precio, 0);
    const agot = inventario().filter((p) => p.stock <= 0).length;
    const bajos = inventario().filter((p) => p.stock > 0 && p.stock <= p.minimo).length;
    const mes = MESES[Number(d.h.slice(5, 7)) - 1];
    const chipStock = agot ? `<span class="chip ch-down">${agot} agotados</span>` : bajos ? `<span class="chip ch-warn">${bajos} bajos</span>` : `<span class="chip ch-up">✓ todo ok</span>`;
    const kpis = [
      kpi("💵", "Ventas de hoy", usd(suma(vHoy, "total_usd")), `${bs(suma(vHoy, "total_bs"))}, ${vHoy.length} venta(s)`, chipVariacion(suma(vHoy, "total_usd"), suma(vAyer, "total_usd")), "linear-gradient(90deg,#60c5e3,#0ea5e9)"),
      kpi("📈", `Ventas de ${mes}`, usd(usdMes), `${bs(suma(vMes, "total_bs"))}, ${vMes.length} venta(s)`, "", "linear-gradient(90deg,#7c3aed,#a78bfa)"),
      kpi("💎", "Utilidad bruta del mes", usd(util), `Ventas netas ${usd(neto)} − costo ${usd(costo)}`, neto > 0 ? `<span class="chip ${margen >= 25 ? "ch-up" : "ch-warn"}">${f2.format(margen)}% margen</span>` : `<span class="chip ch-flat">sin ventas</span>`, "linear-gradient(90deg,#2fd47a,#4ade80)"),
      kpi("🧾", "Ticket promedio", usd(vMes.length ? usdMes / vMes.length : 0), "Promedio por venta en el mes", "", "linear-gradient(90deg,#ffb020,#fbbf24)"),
      kpi("🏬", "Inventario a costo", usd(valCosto), `≈ ${bs(r2(valCosto * S.tasa))}`, "", "linear-gradient(90deg,#14b8a6,#2dd4bf)"),
      kpi("🏷️", "Inventario a precio de venta", usd(valVenta), `Ganancia potencial ${usd(valVenta - valCosto)}`, "", "linear-gradient(90deg,#ec4899,#f472b6)"),
      kpi("📥", "Compras del mes", usd(suma(d.compras, "total_usd")), `${d.compras.length} compra(s) a proveedores`, "", "linear-gradient(90deg,#6366f1,#818cf8)"),
      kpi("⚠️", "Productos por reponer", String(agot + bajos), `de ${S.productos.length} productos activos`, chipStock, "linear-gradient(90deg,#ff4d5e,#f97316)"),
    ].join("");

    const tasas = Object.fromEntries(d.emit.map((v) => [v.id, Number(v.tasa_bcv) || S.tasa]));
    const metodos = {};
    d.pagos.forEach((p) => { metodos[p.metodo] = (metodos[p.metodo] || 0) + (p.moneda === "USD" ? Number(p.monto) : Number(p.monto) / (tasas[p.venta_id] || S.tasa)); });
    const totalPagos = Object.values(metodos).reduce((a, b) => a + b, 0) || 1;
    const pagos = Object.entries(metodos).sort((a, b) => b[1] - a[1])
      .map(([n, v]) => ({ nombre: n, valor: v, texto: usd(v), sub: `${f2.format(v / totalPagos * 100)}% de lo cobrado` }));

    const prods = {};
    d.detalle.forEach((x) => {
      const p = prods[x.descripcion] || (prods[x.descripcion] = { usd: 0, und: 0, util: 0 });
      p.usd += Number(x.subtotal_usd); p.und += Number(x.cantidad);
      p.util += Number(x.subtotal_usd) - Number(x.cantidad) * Number(x.costo_unitario_usd || 0);
    });
    const top = Object.entries(prods).sort((a, b) => b[1].usd - a[1].usd).slice(0, 5)
      .map(([n, v]) => ({ nombre: n, valor: v.usd, texto: usd(v.usd), sub: `${v.und} und. vendidas, utilidad ${usd(v.util)}` }));

    const reponer = inventario().filter((p) => p.stock <= p.minimo).sort((a, b) => a.stock - b.stock).slice(0, 6);
    const listaReponer = reponer.length ? reponer.map((p) => `<button class="fila-dash" data-a="detalle" data-v="${p.id}">
        <div class="fd-cuerpo"><div class="fd-n">${esc(p.nombre)}</div><div class="fd-s">${esc(p.sku)}</div>
          <div class="mini-pista"><div style="width:${Math.max(0, Math.min(p.stock / (p.minimo || 1), 1)) * 100}%;background:${p.stock <= 0 ? "var(--freno)" : "var(--ambar)"}"></div></div></div>
        ${p.stock <= 0 ? `<span class="chip ch-down">Agotado</span>` : `<span class="chip ch-warn">${p.stock} / mín ${p.minimo}</span>`}</button>`).join("")
      : `<div class="vacio-mini">✅ Todo el inventario está sobre el mínimo.</div>`;

    const ultimas = d.ventas.slice(0, 5);
    const listaUltimas = ultimas.length ? ultimas.map((v) => `<button class="fila-dash" data-a="verVentaDia" data-v="${v.id}">
        <div class="fd-cuerpo"><div class="fd-n">${esc(v.cliente_nombre)} ${v.estado === "ANULADA" ? `<span class="chip ch-down">Anulada</span>` : ""}</div>
          <div class="fd-s">${esc(v.numero)}, ${fechaHora(v.fecha)}</div></div>
        <div class="fd-der" style="${v.estado === "ANULADA" ? "text-decoration:line-through;opacity:.5" : ""}"><b class="num">${usd(v.total_pagar_usd)}</b><small>${bs(v.total_pagar_bs)}</small></div></button>`).join("")
      : `<div class="vacio-mini">Aún no hay ventas registradas.</div>`;

    return `<div class="kpis">${kpis}</div>
      ${panel("📊 Ventas de los últimos 30 días", "Total diario en dólares (incluye IVA)", graficoVentas(d))}
      ${panel("💳 Formas de pago", "Cobrado en el mes, equivalente en USD", barrasLista(pagos, "Sin pagos este mes."))}
      ${panel("🏆 Productos más vendidos", "Top 5 del mes por monto vendido (sin IVA)", barrasLista(top, "Sin ventas este mes."))}
      ${panel("🚨 Por reponer", "Productos agotados o en su stock mínimo", listaReponer)}
      ${panel("🧾 Últimas ventas", "Los movimientos más recientes", listaUltimas)}`;
  }
  async function pantallaInicio() {
    $("#main").innerHTML = `${heroInicio()}${avisoTasa()}
      <div class="accesos">
        <button class="btn btn-haz" data-a="tab" data-v="vender">🛒 Nueva venta</button>
        <button class="btn" data-a="tab" data-v="productos">📦 Productos</button>
        <button class="btn" data-a="tab" data-v="ventas">🧾 Ventas</button>
        ${puedeEscanear() ? `<button class="btn" data-a="escanear" data-v="vender">${ICO.scan} Escanear</button>` : `<button class="btn" data-a="tab" data-v="productos">🔍 Buscar precio</button>`}
      </div>
      <div id="dash"><div class="vacio-mini">Preparando tu panel…</div></div>
      ${bloqueInstalar()}
      <p style="text-align:center;margin-top:18px"><button class="link" data-a="salir">Cerrar sesión</button></p>`;
    let d;
    try { d = await datosDashboard(); } catch (e) {
      if ($("#dash")) $("#dash").innerHTML = `<div class="aviso">No se pudo cargar el panel: ${esc(e.message || e)}</div>`;
      return;
    }
    if (S.tab !== "inicio" || !$("#dash")) return;
    $("#dash").innerHTML = htmlDashboard(d);
    const anterior = d.tasas.find((t) => String(t.fecha).slice(0, 10) < S.fechaTasa);
    if (anterior && $("#chipTasa")) $("#chipTasa").innerHTML = chipVariacion(S.tasa, Number(anterior.tasa));
  }

  // ------------------------------------------------------------------ VENDER y PRODUCTOS
  function barraBusqueda(destino) {
    return `<div class="buscar">
      <input id="q" type="search" placeholder="Busca por nombre, código o marca" autocomplete="off" enterkeyhint="search" value="${esc(S.q)}" aria-label="Buscar producto">
      ${puedeEscanear() ? `<button class="btn" data-a="escanear" data-v="${destino}" aria-label="Escanear código de barras">${ICO.scan}</button>` : ""}
    </div><div class="lista" id="lista"></div>`;
  }
  function pantallaVender() {
    $("#main").innerHTML = `<h1 class="titulo">Vender</h1>
      <p class="sub">Toca <b>+</b> para agregar. Cada toque suma una unidad.</p>${barraBusqueda("vender")}`;
    renderLista();
  }
  function iniciales(nombre) {
    return String(nombre || "?").replace(/[^A-Za-zÁÉÍÓÚÑáéíóúñ0-9 ]/g, " ").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase() || "?";
  }
  const estadoStock = (p) => (p.servicio ? "ok" : p.stock <= 0 ? "cero" : p.stock <= p.minimo ? "bajo" : "ok");
  function pantallaProductos() {
    const agot = inventario().filter((p) => p.stock <= 0).length;
    const repo = inventario().filter((p) => p.stock <= p.minimo).length;
    const filtros = [["todos", "Todos", S.productos.length], ["reponer", "Por reponer", repo], ["agotados", "Agotados", agot]];
    $("#main").innerHTML = `
      <div class="enc">
        <div><h1 class="titulo">Productos</h1><p class="sub" style="margin:0">Precios, stock y fichas</p></div>
        ${puedeCrear() ? `<button class="btn btn-haz btn-mini" data-a="nuevoProd">+ Nuevo</button>` : ""}
      </div>
      <div class="filtros" role="tablist">${filtros.map(([id, txt, n]) =>
        `<button class="filtro ${S.filtroProd === id ? "activo" : ""}" data-a="filtroProd" data-v="${id}" role="tab" aria-selected="${S.filtroProd === id}">${txt}<span>${n}</span></button>`).join("")}</div>
      ${barraBusqueda("productos")}`;
    renderLista();
  }
  function tarjetaProducto(p) {
    const est = estadoStock(p);
    const pct = p.servicio ? 100 : Math.max(0, Math.min(p.stock / (Math.max(p.minimo, 1) * 3), 1)) * 100;
    const txt = p.servicio ? "Servicio, sin inventario" : est === "cero" ? "Agotado" : est === "bajo" ? `Quedan ${p.stock}, mínimo ${p.minimo}` : `${p.stock} en stock`;
    return `<button class="pcard" data-a="detalle" data-v="${p.id}">
      <div class="pav ${est}">${esc(iniciales(p.nombre))}</div>
      <div class="pcuerpo">
        <div class="pnombre">${esc(p.nombre)}</div>
        <div class="pmeta"><span class="sku">${esc(p.sku)}</span>${p.marca ? `<span class="pmarca">${esc(p.marca)}</span>` : ""}</div>
        <div class="pstock ${est}"><div class="mini-pista"><div style="width:${pct.toFixed(0)}%"></div></div><span>${txt}</span></div>
      </div>
      <div class="pprecio"><span class="num">${usd(p.precio)}</span><small>${bs(r2(p.precio * S.tasa))}</small></div>
    </button>`;
  }
  function renderLista() {
    const el = $("#lista");
    if (!el) return;
    let res = buscar(S.q, S.tab === "productos" ? 400 : 40);
    if (S.tab === "productos") {
      if (S.filtroProd === "reponer") res = res.filter((p) => !p.servicio && p.stock <= p.minimo);
      if (S.filtroProd === "agotados") res = res.filter((p) => !p.servicio && p.stock <= 0);
      res = res.slice(0, 60);
    }
    if (!res.length) {
      const crear = puedeCrear() && S.q ? `<div style="margin-top:14px"><button class="btn btn-haz btn-ancho" data-a="nuevoProd" data-v="busqueda">+ Crear “${esc(S.q)}” como producto nuevo</button></div>` : "";
      el.innerHTML = S.q ? `<div class="vacio"><b>Nada coincide con “${esc(S.q)}”</b>Prueba con otra palabra o con el código.${crear}</div>`
        : S.filtroProd !== "todos" && S.tab === "productos" ? `<div class="vacio"><b>¡Nada por aquí!</b>No hay productos en este grupo.</div>`
        : `<div class="vacio"><b>No hay productos activos</b>Toca “Nuevo” para agregar el primero.</div>`;
      return;
    }
    if (S.tab === "productos") {
      el.innerHTML = res.map(tarjetaProducto).join("") + (res.length === 60 ? `<p class="sub" style="text-align:center">Escribe en el buscador para ver más productos.</p>` : "");
      return;
    }
    el.innerHTML = res.map((p) => {
      const c = enVenta(p.id);
      const bloqueado = !p.servicio && p.stock <= 0 && !permiteSinStock();
      return `<div class="item ${c ? "en-venta" : ""}">
        <div class="cuerpo"><div class="nombre">${esc(p.nombre)}</div><div class="meta">${esc(p.sku)} ${chipStock(p)}</div></div>
        <div class="precio"><span class="num">${usd(p.precio)}</span><small>${bs(r2(p.precio * S.tasa))}</small></div>
        <button class="mas" data-a="agregar" data-v="${p.id}" ${bloqueado ? "disabled" : ""} aria-label="Agregar ${esc(p.nombre)}">+${c ? `<span class="cant">${c}</span>` : ""}</button></div>`;
    }).join("") + (res.length === 40 ? `<p class="sub" style="text-align:center">Escribe en el buscador para ver más productos.</p>` : "");
  }
  function agregar(id, silencioso = false) {
    const p = prod(id);
    if (!p) return false;
    const item = S.cart.find((i) => i.id === id);
    const actual = item ? item.cantidad : 0;
    if (p.precio <= 0) { toast(`${p.nombre} no tiene precio fijo: cóbralo desde el sistema en la PC`, true); return false; }
    if (!p.servicio && actual + 1 > p.stock && !permiteSinStock()) {
      toast(p.stock <= 0 ? `${p.nombre} está agotado` : `Solo hay ${p.stock} disponible${p.stock === 1 ? "" : "s"}`, true);
      return false;
    }
    if (item) item.cantidad += 1;
    else S.cart.push({ id: p.id, sku: p.sku, nombre: p.nombre, precio: p.precio, precioFinal: null, exento: p.exento, stock: p.stock, servicio: p.servicio, cantidad: 1 });
    if (navigator.vibrate) navigator.vibrate(12);
    if (!silencioso) toast(`Agregado: ${p.nombre}`);
    renderLista();
    renderTotalbar();
    return true;
  }

  // ------------------------------------------------------------------ hojas (pantallas emergentes)
  function abrirHoja(nombre) {
    const nueva = sheetEl.hidden;
    S.hoja = nombre;
    renderHoja(nueva);
  }
  function cerrarHoja() {
    detenerCamara();
    S.editPrecio = null;
    S.hoja = null;
    sheetEl.hidden = true;
    sheetEl.innerHTML = "";
    if (S.tab === "vender" || S.tab === "productos") renderLista();
    renderTotalbar();
  }
  function renderHoja(animar = false) {
    const builders = { venta: hojaVenta, cobro: hojaCobro, exito: hojaExito, producto: hojaProducto, ventaDia: hojaVentaDia, escaner: hojaEscaner, nuevoProd: hojaNuevoProd };
    const fn = builders[S.hoja];
    if (!fn) return cerrarHoja();
    const r = fn();
    if (!r) return;
    const scroll = $(".hoja-cuerpo") ? $(".hoja-cuerpo").scrollTop : 0;
    sheetEl.innerHTML = `<div class="hoja ${animar ? "anim" : ""}" role="dialog" aria-modal="true" aria-label="${esc(r.titulo)}">
      <div class="hoja-cab"><h2>${esc(r.titulo)}</h2><button class="cerrar" data-a="cerrar" aria-label="Cerrar">✕</button></div>
      <div class="hoja-cuerpo">${r.cuerpo}</div>${r.pie ? `<div class="hoja-pie">${r.pie}</div>` : ""}</div>`;
    sheetEl.hidden = false;
    if (!animar) $(".hoja-cuerpo").scrollTop = scroll;
  }

  // ----- Venta actual
  const precioCobrado = (i) => (i.precioFinal != null ? i.precioFinal : i.precio);
  const descMax = () => Number(S.cfg.descuento_max_pct ?? 10);
  function infoDescuento(i, valor) {
    if (!(valor > 0)) return "Escribe el precio que le vas a cobrar por unidad.";
    if (valor > i.precio) return `<span style="color:var(--freno)">No puede ser mayor que el precio normal (${usd(i.precio)}).</span>`;
    const pct = (1 - valor / i.precio) * 100;
    if (pct < 0.005) return "Es el precio normal, sin descuento.";
    const linea = `Descuento de ${usd(r2(i.precio - valor))} por unidad (${f2.format(pct)}%). Equivale a ${bs(r2(valor * S.tasa))}.`;
    return pct > descMax() + 1e-9
      ? `<span style="color:var(--freno)">${linea} Supera el descuento máximo permitido (${f2.format(descMax())}%). Puedes subirlo en Configuración del sistema.</span>`
      : linea;
  }
  function hojaVenta() {
    if (!S.cart.length) { cerrarHoja(); return null; }
    const t = calc([]);
    const descTotal = r2(S.cart.reduce((a, i) => a + (i.precio - precioCobrado(i)) * i.cantidad, 0));
    const lineas = S.cart.map((i) => {
      const pf = i.precioFinal != null;
      const editor = S.editPrecio === i.id ? `<div class="editor-precio">
          <label class="campo"><span>Precio que le cobras por unidad ($)</span>
            <input id="inPrecio" data-f="precioFinal" inputmode="decimal" value="${esc(S.precioEdit)}" placeholder="${f2.format(i.precio)}"></label>
          <p class="sub" id="infoDesc" style="margin-top:-6px">${infoDescuento(i, parseMonto(S.precioEdit))}</p>
          <div class="fila-btn">
            <button class="btn btn-haz btn-mini" data-a="guardarPrecio" data-v="${i.id}">Aplicar precio</button>
            ${pf ? `<button class="btn btn-lin btn-mini" data-a="quitarDesc" data-v="${i.id}">Precio normal</button>` : ""}
            <button class="btn btn-lin btn-mini" data-a="cancelPrecio">Cancelar</button>
          </div></div>` : "";
      return `<div class="linea">
        <div class="cuerpo"><div class="nombre">${esc(i.nombre)}</div>
          <div class="meta">${pf ? `<s>${usd(i.precio)}</s> <b class="precio-desc">${usd(i.precioFinal)}</b> c/u` : `${usd(i.precio)} c/u`}</div>
          <div class="linea-acc">
            <button class="quitar" data-a="quitar" data-v="${i.id}">Quitar</button>
            <button class="ajustar" data-a="editPrecio" data-v="${i.id}">${pf ? "Cambiar precio" : "Cambiar precio"}</button>
          </div></div>
        <div class="cantidad">
          <button data-a="menos" data-v="${i.id}" aria-label="Restar una unidad">−</button>
          <span class="num">${i.cantidad}</span>
          <button data-a="mas1" data-v="${i.id}" aria-label="Sumar una unidad">+</button>
        </div>
      </div>${editor}`;
    }).join("");
    const igtf = t.igtfPct ? `<div class="fila"><span>Si paga en divisas (con IGTF)</span><span>${usd(t.todoDivisas)}</span></div>` : "";
    const iva = S.aplicaIva ? `<div class="fila"><span>IVA ${t.ivaPct}%</span><span>${bs(t.ivaBs)}</span></div>` : "";
    const desc = descTotal > 0 ? `<div class="fila" style="color:var(--verde)"><span>Descuentos aplicados</span><span>−${usd(descTotal)}</span></div>` : "";
    return {
      titulo: "Venta actual",
      cuerpo: `${lineas}
        <div class="interruptor">
          <div><b>Cobrar IVA (${Number(S.cfg.iva_porcentaje || 16)}%)</b>
          <small>${S.aplicaIva ? "Sale como factura con IVA" : "Sale como nota de entrega sin IVA"}</small></div>
          <button class="switch ${S.aplicaIva ? "on" : ""}" data-a="iva" role="switch" aria-checked="${S.aplicaIva}" aria-label="Cobrar IVA"></button>
        </div>
        <div class="resumen">
          ${desc}
          <div class="fila"><span>Subtotal</span><span>${bs(t.baseBs + t.exBs)}</span></div>
          ${iva}
          <div class="fila total"><span>Total</span><span class="num">${bs(t.totalBs)}</span></div>
          <div class="fila"><span>Equivalente</span><span>${usd(t.totalUsd)}</span></div>
          ${igtf}
        </div>
        ${tasaBloqueada() ? `<div class="aviso" style="margin-top:12px">La tasa BCV está vencida. Actualízala en el sistema principal para poder cobrar.</div>` : ""}`,
      pie: `<button class="btn btn-haz btn-ancho" data-a="cobrar" ${tasaBloqueada() ? "disabled" : ""}>Cobrar ${bs(t.totalBs)}</button>
            <button class="btn btn-lin btn-ancho" data-a="cerrar">Seguir agregando</button>`,
    };
  }

  // ----- Cobro: 1. Cliente  2. Pago
  function pasos(n) {
    return `<div class="pasos"><div class="paso ${n === 1 ? "activo" : "hecho"}">${n > 1 ? "✓ " : ""}1. Cliente</div>
      <div class="paso ${n === 2 ? "activo" : ""}">2. Pago</div></div>`;
  }
  function hojaCobro() {
    return S.cobroPaso === 1 ? hojaCliente() : hojaPago();
  }
  function hojaCliente() {
    const c = S.cliente;
    const conRif = c.modo === "rif";
    const tipos = ["V", "E", "J", "G", "P"].map((t) => `<option ${t === c.tipo ? "selected" : ""}>${t}</option>`).join("");
    return {
      titulo: "Cobrar",
      cuerpo: `${pasos(1)}
        <div class="segmento">
          <button class="${!conRif ? "activo" : ""}" data-a="cliModo" data-v="final">Consumidor final</button>
          <button class="${conRif ? "activo" : ""}" data-a="cliModo" data-v="rif">Con cédula o RIF</button>
        </div>
        ${!conRif ? `<p class="sub">La venta sale a nombre de consumidor final. Es lo más rápido para el mostrador.</p>` : `
          <div class="fila-campos">
            <label class="campo"><span>Tipo</span><select data-f="tipo">${tipos}</select></label>
            <label class="campo"><span>Número</span><input data-f="numero" inputmode="numeric" value="${esc(c.numero)}" placeholder="12345678"></label>
          </div>
          <p class="sub" id="cliEstado" style="margin-top:-6px"></p>
          <label class="campo"><span>Nombre o razón social</span><input data-f="nombre" id="cliNombre" value="${esc(c.nombre)}" autocomplete="off"></label>
          <label class="campo"><span>Teléfono (para enviarle el comprobante por WhatsApp)</span>
            <input data-f="telefono" id="cliTel" type="tel" inputmode="tel" value="${esc(c.telefono)}" placeholder="0414 1234567"></label>`}`,
      pie: `<button class="btn btn-haz btn-ancho" data-a="aPago">Continuar al pago</button>`,
    };
  }
  async function buscarCliente() {
    const rif = normalizarRif(S.cliente.tipo, S.cliente.numero);
    const estado = $("#cliEstado");
    if (!estado) return;
    if (!rif) { estado.textContent = S.cliente.numero ? "La cédula o RIF debe tener entre 5 y 9 dígitos." : ""; return; }
    estado.textContent = "Buscando…";
    const { data } = await sb.from("clientes").select("nombre, telefono").eq("rif", rif).limit(1);
    const cli = (data || [])[0];
    if (cli) {
      S.cliente.nombre = cli.nombre;
      if (!S.cliente.telefono && cli.telefono) S.cliente.telefono = cli.telefono;
      if ($("#cliNombre")) $("#cliNombre").value = S.cliente.nombre;
      if ($("#cliTel")) $("#cliTel").value = S.cliente.telefono;
      estado.textContent = `Cliente registrado: ${rif}`;
    } else {
      estado.textContent = `${rif} es un cliente nuevo. Se guardará al confirmar la venta.`;
    }
  }
  function hojaPago() {
    const t = calc();
    const m = METODOS.find((x) => x.id === S.metodo) || METODOS[0];
    const pct = t.totalBs > 0 ? Math.min(Math.max(1 - t.faltaBs / t.totalBs, 0), 1) : 0;
    const exacto = montoExacto(m.moneda);
    const quien = S.cliente.modo === "final" ? "Consumidor final" : `${S.cliente.nombre} (${normalizarRif(S.cliente.tipo, S.cliente.numero)})`;
    const pagos = S.pagos.map((p, i) => `<div class="pago"><div><b>${esc(p.metodo)}</b>${p.referencia ? `<small>Ref. ${esc(p.referencia)}</small>` : ""}</div>
      <div style="display:flex;align-items:center;gap:10px"><span class="num" style="font-size:1.15rem;font-weight:700">${p.moneda === "USD" ? usd(p.monto) : bs(p.monto)}</span>
      <button class="cerrar" style="width:34px;height:34px;font-size:.9rem" data-a="quitarPago" data-v="${i}" aria-label="Quitar pago">✕</button></div></div>`).join("");
    let accion;
    if (!t.completo) {
      accion = `<p style="margin:14px 0 4px;font-weight:600">¿Cómo paga?</p>
        <div class="metodos">${METODOS.map((x) => `<button class="metodo ${x.id === m.id ? "activo" : ""}" data-a="metodo" data-v="${esc(x.id)}">${x.ico} ${esc(x.id)}</button>`).join("")}</div>
        ${m.ref ? `<label class="campo"><span>Número de referencia</span><input data-f="ref" inputmode="numeric" value="${esc(S.pagoRef)}" placeholder="Últimos dígitos"></label>` : ""}
        <button class="btn btn-haz btn-ancho" data-a="pagoExacto">Cobrar exacto: ${m.moneda === "USD" ? usd(exacto) : bs(exacto)}</button>
        <p style="text-align:center;margin:6px 0 0"><button class="link" data-a="togglePar">${S.verParcial ? "Ocultar pago parcial" : "Pago parcial o mixto"}</button></p>
        ${S.verParcial ? `<label class="campo"><span>Monto recibido en ${m.moneda === "USD" ? "dólares" : "bolívares"}</span>
            <input data-f="monto" inputmode="decimal" value="${esc(S.pagoMonto)}" placeholder="0,00"></label>
          <button class="btn btn-ancho" data-a="pagoParcial">Agregar este pago</button>` : ""}`;
    } else {
      const vuelto = [t.vueltoUsd > 0 ? usd(t.vueltoUsd) : "", t.vueltoBs > 0 ? bs(t.vueltoBs) : ""].filter(Boolean).join(" + ");
      accion = vuelto ? `<div class="vuelto">Vuelto a entregar<span class="num">${vuelto}</span></div>`
                      : `<div class="vuelto">Pago completo</div>`;
      if (t.igtfUsd > 0) accion += `<p class="sub" style="text-align:center">Incluye IGTF de ${usd(t.igtfUsd)} por el pago en divisas.</p>`;
    }
    return {
      titulo: "Cobrar",
      cuerpo: `${pasos(2)}
        <p class="sub" style="margin-bottom:6px">Cliente: <b>${esc(quien)}</b></p>
        <div class="grande"><div class="et">Total a cobrar</div><div class="num">${bs(t.totalBs)}</div>
          <small>${usd(t.totalUsd)} a Bs. ${f4.format(S.tasa)}${t.igtfPct ? `. En divisas: ${usd(t.todoDivisas)} con IGTF` : ""}</small></div>
        <div class="barra"><div style="width:${(t.completo ? 1 : pct) * 100}%"></div></div>
        <div class="barra-txt"><span>Pagado ${Math.round((t.completo ? 1 : pct) * 100)}%</span><span>${t.completo ? "Listo" : "Falta " + bs(t.faltaBs)}</span></div>
        ${pagos}${accion}`,
      pie: `<button class="btn btn-verde btn-ancho" data-a="confirmar" ${t.completo && !S.enviando ? "" : "disabled"}>${S.enviando ? "Registrando…" : "Confirmar venta"}</button>
            <button class="btn btn-lin btn-ancho" data-a="aCliente">Volver al cliente</button>`,
    };
  }
  function registrarPago(monto) {
    const m = METODOS.find((x) => x.id === S.metodo) || METODOS[0];
    if (m.ref && !S.pagoRef.trim()) return toast(`${m.id} necesita el número de referencia`, true);
    if (!(monto > 0)) return toast("Escribe un monto mayor que cero", true);
    S.pagos.push({ metodo: m.id, moneda: m.moneda, monto: r2(monto), referencia: S.pagoRef.trim() });
    S.pagoRef = ""; S.pagoMonto = ""; S.verParcial = false;
    renderHoja();
  }
  async function confirmar() {
    if (S.enviando) return;
    S.enviando = true; renderHoja();
    const c = S.cliente;
    const cliente = c.modo === "final" ? { rif: "", nombre: "CONSUMIDOR FINAL" }
      : { rif: normalizarRif(c.tipo, c.numero), nombre: c.nombre.trim(), telefono: c.telefono.trim(), direccion: "" };
    const params = {
      p_items: S.cart.map((i) => ({ producto_id: i.id, cantidad: i.cantidad,
        descuento_pct: i.precioFinal != null ? Number(((1 - i.precioFinal / i.precio) * 100).toFixed(10)) : 0 })),
      p_pagos: S.pagos, p_cliente: cliente, p_observaciones: null,
      p_idempotency_key: S.ventaKey, p_aplicar_iva: S.aplicaIva,
    };
    let { data, error } = await sb.rpc("registrar_venta", params);
    // Diferencia de céntimos por redondeo: se ajusta el último pago en Bs y se reintenta una vez
    const m = error && /faltan Bs\. ([\d.]+)/.exec(error.message || "");
    if (m && Number(m[1]) <= 0.05) {
      const ves = [...S.pagos].reverse().find((p) => p.moneda === "VES");
      if (ves) { ves.monto = r2(ves.monto + Number(m[1])); ({ data, error } = await sb.rpc("registrar_venta", params)); }
    }
    if (error) {
      S.enviando = false; renderHoja();
      return toast(error.message || "No se pudo registrar la venta", true);
    }
    const id = data.venta_id;
    const [v, d, p] = await Promise.all([
      sb.from("ventas").select("*").eq("id", id).single(),
      sb.from("detalle_ventas").select("sku, descripcion, cantidad, precio_unitario_usd, subtotal_usd").eq("venta_id", id),
      sb.from("pagos_venta").select("metodo, moneda, monto, referencia").eq("venta_id", id),
    ]);
    S.ultima = { venta: v.data, detalle: d.data || [], pagos: p.data || [], telefono: c.modo === "rif" ? c.telefono : "" };
    S.cart = []; S.pagos = []; S.enviando = false; S.ventaKey = uuid(); S.cobroPaso = 1;
    S.cliente = { modo: "final", tipo: "V", numero: "", nombre: "", telefono: "" };
    S.aplicaIva = esV(S.cfg.iva_por_defecto ?? "true");
    if (navigator.vibrate) navigator.vibrate([20, 60, 20]);
    abrirHoja("exito");
    cargarProductos().then(() => { if (!S.hoja && (S.tab === "vender" || S.tab === "productos")) renderLista(); }).catch(() => {});
  }

  // ----- Éxito y WhatsApp
  function hojaExito() {
    const v = S.ultima && S.ultima.venta;
    if (!v) { cerrarHoja(); return null; }
    const vuelto = [Number(v.vuelto_usd) > 0 ? usd(v.vuelto_usd) : "", Number(v.vuelto_bs) > 0 ? bs(v.vuelto_bs) : ""].filter(Boolean).join(" + ");
    return {
      titulo: "Venta registrada",
      cuerpo: `<div class="exito"><div class="check">✓</div><h2>${esc(v.numero)}</h2>
          <div class="doc">${esc(v.cliente_nombre)}${v.aplica_iva === false ? ", nota de entrega" : ""}</div></div>
        <div class="grande"><div class="num">${bs(v.total_pagar_bs)}</div><small>${usd(v.total_pagar_usd)}</small></div>
        ${vuelto ? `<div class="vuelto">Vuelto a entregar<span class="num">${vuelto}</span></div>` : ""}`,
      pie: `<button class="btn btn-verde btn-ancho" data-a="whatsapp">Enviar comprobante por WhatsApp</button>
            <button class="btn btn-haz btn-ancho" data-a="nuevaVenta">Nueva venta</button>`,
    };
  }
  function textoComprobante(v, detalle, pagos) {
    const L = [];
    L.push(`*${S.cfg.empresa_nombre || "SERVICIOS AUTOS LED"}*`);
    if (S.cfg.empresa_rif) L.push(`RIF: ${S.cfg.empresa_rif}`);
    L.push("");
    L.push(`${v.aplica_iva === false ? "Nota de entrega" : "Comprobante"} N° ${v.numero}`);
    L.push(`Fecha: ${fechaHora(v.fecha)}`);
    L.push(`Cliente: ${v.cliente_nombre} (${v.cliente_rif})`);
    L.push("");
    detalle.forEach((d) => L.push(`${d.cantidad} x ${d.descripcion}  ${usd(d.subtotal_usd)}`));
    L.push("");
    if (Number(v.iva_usd) > 0) L.push(`IVA ${Number(v.iva_porcentaje)}%: ${bs(v.iva_bs)}`);
    if (Number(v.igtf_usd) > 0) L.push(`IGTF: ${bs(v.igtf_bs)}`);
    L.push(`*Total: ${bs(v.total_pagar_bs)}*`);
    L.push(`Equivalente: ${usd(v.total_pagar_usd)}`);
    L.push(`Tasa BCV: Bs. ${f4.format(v.tasa_bcv)} (fecha valor ${dmy(String(v.fecha_tasa))})`);
    pagos.forEach((p) => L.push(`Pago: ${p.metodo} ${p.moneda === "USD" ? usd(p.monto) : bs(p.monto)}`));
    L.push("");
    L.push("¡Gracias por su compra!");
    return L.join("\n");
  }
  function abrirWhatsApp(texto, telefono) {
    let tel = String(telefono || "").replace(/\D/g, "");
    if (tel.startsWith("0")) tel = "58" + tel.slice(1);
    else if (tel.length === 10 && tel.startsWith("4")) tel = "58" + tel;
    window.open(`https://wa.me/${tel}?text=${encodeURIComponent(texto)}`, "_blank");
  }

  // ----- Ficha de producto
  function hojaProducto() {
    const p = prod(S.prodSel);
    if (!p) { cerrarHoja(); return null; }
    const est = estadoStock(p);
    const bloqueado = !p.servicio && p.stock <= 0 && !permiteSinStock();
    const ivaPct = Number(S.cfg.iva_porcentaje || 16);
    const colorStock = est === "cero" ? "var(--freno)" : est === "bajo" ? "var(--ambar)" : "var(--verde)";
    const margen = p.precio > 0 && p.costo > 0 ? (p.precio - p.costo) / p.precio * 100 : null;
    const admin = puedeCrear();
    return {
      titulo: "Ficha del producto",
      cuerpo: `<div class="ficha-cab">
          <div class="pav grande ${est}">${esc(iniciales(p.nombre))}</div>
          <div style="min-width:0"><h2 class="ficha-nombre">${esc(p.nombre)}</h2>
            <div class="pmeta"><span class="sku">${esc(p.sku)}</span>${p.marca ? `<span class="pmarca">${esc(p.marca)}</span>` : ""}${p.exento ? `<span class="pmarca">Exento de IVA</span>` : ""}</div></div>
        </div>
        <div class="ficha-precio">
          <div class="kpi-et">Precio de venta</div>
          <div class="num fp-usd">${usd(p.precio)}</div>
          <div class="fp-bs">${bs(r2(p.precio * S.tasa))} a la tasa de hoy</div>
          ${p.exento ? "" : `<div class="fp-iva">Con IVA ${ivaPct}%: <b>${usd(r2(p.precio * (1 + ivaPct / 100)))}</b>, ${bs(r2(r2(p.precio * S.tasa) * (1 + ivaPct / 100)))}</div>`}
        </div>
        <div class="cifras">
          ${p.servicio ? `<div class="cifra"><div class="et">Tipo</div><div class="num">🛠️</div><small>servicio, sin inventario</small></div>` : `
          <div class="cifra"><div class="et">En stock</div><div class="num" style="color:${colorStock}">${p.stock}</div><small>${est === "cero" ? "agotado" : est === "bajo" ? "toca reponer" : "unidades"}</small></div>
          <div class="cifra"><div class="et">Stock mínimo</div><div class="num">${p.minimo}</div><small>alerta de reposición</small></div>
          <div class="cifra"><div class="et">Valor en inventario</div><div class="num">${usd(Math.max(p.stock, 0) * p.precio)}</div><small>a precio de venta</small></div>`}
          ${admin ? `<div class="cifra"><div class="et">Costo</div><div class="num">${usd(p.costo)}</div><small>${margen != null ? `margen ${f2.format(margen)}%` : "sin costo registrado"}</small></div>` : ""}
        </div>`,
      pie: `<button class="btn btn-haz btn-ancho" data-a="agregarDetalle" ${bloqueado ? "disabled" : ""}>${bloqueado ? "Agotado" : "Agregar a la venta"}</button>
            <button class="btn btn-lin btn-ancho" data-a="compartirPrecio">Enviar precio por WhatsApp</button>`,
    };
  }

  // ------------------------------------------------------------------ NUEVO PRODUCTO
  function puedeCrear() {
    const lista = String(S.cfg.emails_administradores || "").toLowerCase().split(/[\s,;]+/).filter(Boolean);
    return !lista.length || lista.includes(String((S.user && S.user.email) || "").toLowerCase());
  }
  const usaCategorias = () => esV(S.cfg.usar_categorias ?? "true");
  async function abrirNuevo(prefill = {}) {
    S.nuevo = { autoSku: !prefill.sku, sku: prefill.sku || "", nombre: prefill.nombre || "", marca: "", precio: "",
                costo: "", stock: "1", minimo: "2", exento: false, categoria: "", desde: S.tab };
    S.guardando = false;
    abrirHoja("nuevoProd");
    if (usaCategorias() && !S.categorias) {
      const { data } = await sb.from("categorias").select("id, nombre").order("nombre");
      S.categorias = data || [];
      if (S.hoja === "nuevoProd") renderHoja();
    }
  }
  function infoPrecio(precio, costo) {
    if (!(precio > 0)) return "Escribe el precio para ver su valor en bolívares.";
    let txt = `Precio en bolívares: <b>${bs(r2(precio * S.tasa))}</b>`;
    if (costo > 0) {
      const m = (precio - costo) / precio * 100;
      const color = m < 0 ? "var(--freno)" : m < 15 ? "var(--ambar)" : "var(--verde)";
      txt += `. Margen de ganancia: <b style="color:${color}">${f2.format(m)}%</b>${m < 0 ? " (vendes con pérdida)" : ""}`;
    }
    return txt;
  }
  function hojaNuevoProd() {
    const n = S.nuevo;
    if (!n) { cerrarHoja(); return null; }
    const cats = usaCategorias() ? `<label class="campo"><span>Categoría</span><select data-f="nv_categoria">
        <option value="">Sin categoría</option>
        ${(S.categorias || []).map((c) => `<option value="${c.id}" ${String(c.id) === String(n.categoria) ? "selected" : ""}>${esc(c.nombre)}</option>`).join("")}
      </select></label>` : "";
    const codigo = n.autoSku ? "" : `<div class="buscar" style="position:static;padding:0">
        <input data-f="nv_sku" value="${esc(n.sku)}" placeholder="Escribe o escanea el código" autocomplete="off" aria-label="Código del producto">
        ${puedeEscanear() ? `<button class="btn" data-a="escanear" data-v="codigoNuevo" aria-label="Escanear código">${ICO.scan}</button>` : ""}
      </div>`;
    return {
      titulo: "Nuevo producto",
      cuerpo: `<p class="sub">Queda en el inventario y listo para vender. El stock inicial se registra en el Kardex.</p>
        <div class="interruptor" style="margin:0 0 12px">
          <div><b>Código automático</b><small>${n.autoSku ? "El sistema le asigna uno, por ejemplo PRD-0001" : "Usa el código de barras o el código del proveedor"}</small></div>
          <button class="switch ${n.autoSku ? "on" : ""}" data-a="nvAutoSku" role="switch" aria-checked="${n.autoSku}" aria-label="Código automático"></button>
        </div>
        ${codigo}${cats}
        <label class="campo"><span>Nombre del producto *</span><input data-f="nv_nombre" value="${esc(n.nombre)}" placeholder="Ej: Bombillo LED H4 6000K" autocomplete="off"></label>
        <label class="campo"><span>Marca</span><input data-f="nv_marca" value="${esc(n.marca)}" autocomplete="off"></label>
        <div class="fila-campos" style="grid-template-columns:1fr 1fr">
          <label class="campo"><span>Precio de venta ($) *</span><input data-f="nv_precio" inputmode="decimal" value="${esc(n.precio)}" placeholder="0,00"></label>
          <label class="campo"><span>Costo ($)</span><input data-f="nv_costo" inputmode="decimal" value="${esc(n.costo)}" placeholder="0,00"></label>
        </div>
        <p class="sub" id="nvInfo" style="margin-top:-4px">${infoPrecio(parseMonto(n.precio), parseMonto(n.costo))}</p>
        <div class="fila-campos" style="grid-template-columns:1fr 1fr">
          <label class="campo"><span>Stock inicial</span><input data-f="nv_stock" inputmode="numeric" value="${esc(n.stock)}"></label>
          <label class="campo"><span>Stock mínimo</span><input data-f="nv_minimo" inputmode="numeric" value="${esc(n.minimo)}"></label>
        </div>
        <div class="interruptor">
          <div><b>Exento de IVA</b><small>${n.exento ? "No se le cobra IVA" : "Se le cobra IVA normalmente"}</small></div>
          <button class="switch ${n.exento ? "on" : ""}" data-a="nvExento" role="switch" aria-checked="${n.exento}" aria-label="Exento de IVA"></button>
        </div>`,
      pie: `<button class="btn btn-haz btn-ancho" data-a="nvGuardar" ${S.guardando ? "disabled" : ""}>${S.guardando ? "Guardando…" : n.desde === "vender" ? "Guardar y agregar a la venta" : "Guardar producto"}</button>
            <button class="btn btn-lin btn-ancho" data-a="cerrar">Cancelar</button>`,
    };
  }
  function prefijoCategoria(nombre) {
    const t = norm(nombre).toUpperCase().replace(/[^A-Z0-9]/g, "");
    return (t.slice(0, 3) + "XXX").slice(0, 3);
  }
  async function generarSku(prefijo) {
    const { data, error } = await sb.from("productos").select("sku").ilike("sku", `${prefijo}-%`);
    if (error) throw error;
    const re = new RegExp(`^${prefijo}-(\\d+)$`, "i");
    const max = (data || []).reduce((m, r) => { const x = re.exec(r.sku || ""); return x ? Math.max(m, Number(x[1])) : m; }, 0);
    return `${prefijo}-${String(max + 1).padStart(4, "0")}`;
  }
  async function guardarNuevo() {
    const n = S.nuevo;
    if (!n || S.guardando) return;
    const nombre = n.nombre.trim();
    const precio = parseMonto(n.precio), costo = parseMonto(n.costo);
    const stock = Number(String(n.stock || "0").trim()), minimo = Number(String(n.minimo || "0").trim());
    if (!n.autoSku && !n.sku.trim()) return toast("Escribe el código o activa el código automático", true);
    if (!nombre) return toast("Escribe el nombre del producto", true);
    if (!(precio > 0)) return toast("Escribe el precio de venta", true);
    if (!Number.isInteger(stock) || stock < 0 || !Number.isInteger(minimo) || minimo < 0)
      return toast("El stock debe ser un número entero, sin decimales", true);
    S.guardando = true; renderHoja();
    try {
      const cat = (S.categorias || []).find((c) => String(c.id) === String(n.categoria));
      const sku = n.autoSku ? await generarSku(cat ? prefijoCategoria(cat.nombre) : "PRD") : n.sku.trim().toUpperCase();
      const { data: existe } = await sb.from("productos").select("nombre").eq("sku", sku).limit(1);
      if (existe && existe.length) throw new Error(`El código ${sku} ya pertenece a “${existe[0].nombre}”.`);
      const { data, error } = await sb.from("productos").insert({
        sku, nombre, marca: n.marca.trim() || null, categoria_id: cat ? cat.id : null,
        precio_usd: precio, costo_usd: costo, stock_actual: stock, stock_minimo: minimo,
        exento_iva: n.exento, activo: true,
      }).select("id").single();
      if (error) throw error;
      await cargarProductos();
      S.guardando = false; S.nuevo = null;
      toast(`Producto ${sku} creado`);
      if (n.desde === "vender" && (stock > 0 || permiteSinStock())) {
        cerrarHoja();
        if (S.tab !== "vender") ir("vender");
        agregar(data.id, true);
      } else {
        S.prodSel = data.id;
        S.hoja = "producto";
        renderHoja();
        if (S.tab === "vender" || S.tab === "productos") renderLista();
      }
    } catch (e) {
      S.guardando = false; renderHoja();
      toast(e.message || "No se pudo guardar el producto", true);
    }
  }

  // ------------------------------------------------------------------ VENTAS DEL DÍA
  async function pantallaVentas() {
    S.fechaVentas = S.fechaVentas || hoy();
    $("#main").innerHTML = `<h1 class="titulo">Ventas</h1>
      <label class="campo"><span>Día</span><input type="date" id="fechaVentas" value="${S.fechaVentas}" max="${hoy()}"></label>
      <div id="ventasDia"><p class="sub">Cargando…</p></div>`;
    cargarVentasDia();
  }
  async function cargarVentasDia() {
    const d = S.fechaVentas;
    const { data, error } = await sb.from("ventas")
      .select("id, numero, fecha, cliente_nombre, total_pagar_usd, total_pagar_bs, estado, aplica_iva")
      .gte("fecha", `${d}T00:00:00-04:00`).lte("fecha", `${d}T23:59:59.999-04:00`).order("fecha", { ascending: false });
    const el = $("#ventasDia");
    if (!el || S.tab !== "ventas") return;
    if (error) { el.innerHTML = `<div class="aviso">${esc(error.message)}</div>`; return; }
    const ventas = data || [];
    const ok = ventas.filter((v) => v.estado === "EMITIDA");
    if (!ventas.length) { el.innerHTML = `<div class="vacio"><b>Sin ventas el ${dmy(d)}</b>Las ventas que registres aparecerán aquí.</div>`; return; }
    el.innerHTML = `
      <div class="cifras">
        <div class="cifra"><div class="et">Total del día</div><div class="num">${usd(ok.reduce((a, v) => a + Number(v.total_pagar_usd), 0))}</div>
          <small>${bs(ok.reduce((a, v) => a + Number(v.total_pagar_bs), 0))}</small></div>
        <div class="cifra"><div class="et">Ventas</div><div class="num">${ok.length}</div><small>${ventas.length - ok.length ? `${ventas.length - ok.length} anulada(s)` : "emitidas"}</small></div>
      </div>
      <div class="lista">${ventas.map((v) => `
        <button class="item" data-a="verVentaDia" data-v="${v.id}" style="${v.estado === "ANULADA" ? "opacity:.55" : ""}">
          <div class="cuerpo"><div class="nombre">${esc(v.cliente_nombre)}</div>
            <div class="meta">${esc(v.numero)}, ${hora(v.fecha)} ${v.estado === "ANULADA" ? `<span class="stock cero">Anulada</span>` : v.aplica_iva === false ? `<span class="stock bajo">Sin IVA</span>` : ""}</div></div>
          <div class="precio"><span class="num">${usd(v.total_pagar_usd)}</span><small>${bs(v.total_pagar_bs)}</small></div>
        </button>`).join("")}</div>`;
  }
  async function abrirVentaDia(id) {
    S.ventaDia = null;
    abrirHoja("ventaDia");
    const [v, d, p] = await Promise.all([
      sb.from("ventas").select("*").eq("id", id).single(),
      sb.from("detalle_ventas").select("sku, descripcion, cantidad, precio_unitario_usd, subtotal_usd").eq("venta_id", id),
      sb.from("pagos_venta").select("metodo, moneda, monto, referencia").eq("venta_id", id),
    ]);
    if (S.hoja !== "ventaDia") return;
    S.ventaDia = { venta: v.data, detalle: d.data || [], pagos: p.data || [] };
    renderHoja();
  }
  function hojaVentaDia() {
    if (!S.ventaDia) return { titulo: "Detalle de la venta", cuerpo: `<p class="sub">Cargando…</p>` };
    const { venta: v, detalle, pagos } = S.ventaDia;
    return {
      titulo: v.numero,
      cuerpo: `<p class="sub">${esc(v.cliente_nombre)} (${esc(v.cliente_rif)}), ${fechaHora(v.fecha)}</p>
        ${v.estado === "ANULADA" ? `<div class="aviso">Venta anulada: ${esc(v.motivo_anulacion || "")}</div>` : ""}
        ${detalle.map((d) => `<div class="linea"><div class="cuerpo"><div class="nombre">${esc(d.descripcion)}</div>
          <div class="meta">${d.cantidad} x ${usd(d.precio_unitario_usd)}</div></div><span class="num" style="font-size:1.15rem;font-weight:700">${usd(d.subtotal_usd)}</span></div>`).join("")}
        <div class="resumen">
          ${Number(v.iva_usd) > 0 ? `<div class="fila"><span>IVA ${Number(v.iva_porcentaje)}%</span><span>${bs(v.iva_bs)}</span></div>` : `<div class="fila"><span>IVA</span><span>No aplica</span></div>`}
          ${Number(v.igtf_usd) > 0 ? `<div class="fila"><span>IGTF</span><span>${bs(v.igtf_bs)}</span></div>` : ""}
          <div class="fila total"><span>Total</span><span class="num">${bs(v.total_pagar_bs)}</span></div>
          <div class="fila"><span>Equivalente</span><span>${usd(v.total_pagar_usd)}</span></div>
          <div class="fila"><span>Tasa BCV</span><span>Bs. ${f4.format(v.tasa_bcv)}</span></div>
          ${pagos.map((p) => `<div class="fila"><span>${esc(p.metodo)}${p.referencia ? ` (ref. ${esc(p.referencia)})` : ""}</span><span>${p.moneda === "USD" ? usd(p.monto) : bs(p.monto)}</span></div>`).join("")}
        </div>`,
      pie: v.estado === "ANULADA" ? "" : `<button class="btn btn-verde btn-ancho" data-a="whatsappDia">Enviar por WhatsApp</button>`,
    };
  }

  // ------------------------------------------------------------------ ESCÁNER (Android/Chrome)
  function hojaEscaner() {
    return {
      titulo: "Escanear código",
      cuerpo: `<div class="mira"><video id="video" class="video" playsinline muted></video></div>
        <p class="sub" style="margin-top:10px;text-align:center">Apunta la cámara al código de barras del producto.</p>`,
      pie: `<button class="btn btn-lin btn-ancho" data-a="cerrar">Cancelar</button>`,
    };
  }
  async function abrirEscaner(destino) {
    S.scanDestino = destino;
    abrirHoja("escaner");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      const video = $("#video");
      if (!video || S.hoja !== "escaner") { stream.getTracks().forEach((t) => t.stop()); return; }
      video.srcObject = stream;
      await video.play();
      const formatos = await window.BarcodeDetector.getSupportedFormats();
      camara = { stream, detector: new window.BarcodeDetector({ formats: formatos }) };
      const ciclo = async () => {
        if (!camara) return;
        try {
          const codigos = await camara.detector.detect(video);
          if (codigos.length) { const codigo = codigos[0].rawValue.trim(); detenerCamara(); return manejarCodigo(codigo); }
        } catch (e) { /* cuadro sin código: seguir intentando */ }
        setTimeout(ciclo, 250);
      };
      ciclo();
    } catch (e) {
      cerrarHoja();
      toast("No se pudo abrir la cámara. Revisa el permiso de cámara del navegador.", true);
    }
  }
  function detenerCamara() {
    if (camara) { camara.stream.getTracks().forEach((t) => t.stop()); camara = null; }
  }
  function manejarCodigo(codigo) {
    if (navigator.vibrate) navigator.vibrate(30);
    const p = S.productos.find((x) => x.sku.toUpperCase() === codigo.toUpperCase());
    if (S.scanDestino === "codigoNuevo") {
      if (p) toast(`El código ${codigo} ya pertenece a “${p.nombre}”`, true);
      else { S.nuevo.sku = codigo; S.nuevo.autoSku = false; }
      detenerCamara();
      S.hoja = "nuevoProd";
      return renderHoja();
    }
    cerrarHoja();
    if (!p && puedeCrear()) {
      if (S.scanDestino !== "productos" && S.tab !== "vender") ir("vender");
      abrirNuevo({ sku: codigo });
      return toast(`El código ${codigo} no está registrado. Puedes crearlo ahora.`);
    }
    if (!p) {
      S.q = codigo;
      ir(S.scanDestino === "productos" ? "productos" : "vender");
      return toast(`No hay ningún producto con el código ${codigo}`, true);
    }
    if (S.scanDestino === "productos") { S.prodSel = p.id; return abrirHoja("producto"); }
    if (S.tab !== "vender") ir("vender");
    agregar(p.id);
  }

  // ------------------------------------------------------------------ acciones
  const ACC = {
    tab: (v) => { cerrarHoja(); ir(v); },
    recargar: () => location.reload(),
    salir: async () => { await sb.auth.signOut(); location.reload(); },
    instalar: async () => { if (!instalarEvt) return; instalarEvt.prompt(); await instalarEvt.userChoice; instalarEvt = null; if (S.tab === "inicio") pantallaInicio(); },
    agregar: (v) => agregar(Number(v)),
    detalle: (v) => { S.prodSel = Number(v); abrirHoja("producto"); },
    agregarDetalle: () => { if (agregar(S.prodSel, true)) { toast("Agregado a la venta"); cerrarHoja(); } },
    escanear: (v) => abrirEscaner(v),
    verVenta: () => abrirHoja("venta"),
    cerrar: () => cerrarHoja(),
    menos: (v) => { const i = S.cart.find((x) => x.id === Number(v)); if (i && i.cantidad > 1) i.cantidad -= 1; renderHoja(); },
    mas1: (v) => { const i = S.cart.find((x) => x.id === Number(v)); if (!i) return;
      if (!i.servicio && i.cantidad + 1 > i.stock && !permiteSinStock()) return toast(`Solo hay ${i.stock} disponibles`, true);
      i.cantidad += 1; renderHoja(); },
    quitar: (v) => { S.cart = S.cart.filter((x) => x.id !== Number(v)); S.pagos = []; renderHoja(); renderTotalbar(); },
    iva: () => { S.aplicaIva = !S.aplicaIva; S.pagos = []; renderHoja(); renderTotalbar(); },
    cobrar: () => { S.cobroPaso = 1; S.pagos = []; abrirHoja("cobro"); },
    cliModo: (v) => { S.cliente.modo = v; renderHoja(); },
    aPago: () => {
      const c = S.cliente;
      if (c.modo === "rif") {
        if (!normalizarRif(c.tipo, c.numero)) return toast("La cédula o RIF debe tener entre 5 y 9 dígitos", true);
        if (!c.nombre.trim()) return toast("Escribe el nombre del cliente", true);
      }
      S.cobroPaso = 2; renderHoja();
    },
    aCliente: () => { S.cobroPaso = 1; renderHoja(); },
    metodo: (v) => { S.metodo = v; S.pagoRef = ""; renderHoja(); },
    pagoExacto: () => { const m = METODOS.find((x) => x.id === S.metodo) || METODOS[0]; registrarPago(montoExacto(m.moneda)); },
    togglePar: () => { S.verParcial = !S.verParcial; renderHoja(); },
    pagoParcial: () => registrarPago(parseMonto(S.pagoMonto)),
    quitarPago: (v) => { S.pagos.splice(Number(v), 1); renderHoja(); },
    confirmar: () => confirmar(),
    whatsapp: () => { const u = S.ultima; if (u) abrirWhatsApp(textoComprobante(u.venta, u.detalle, u.pagos), u.telefono); },
    whatsappDia: () => { const u = S.ventaDia; if (u) abrirWhatsApp(textoComprobante(u.venta, u.detalle, u.pagos), ""); },
    nuevaVenta: () => { cerrarHoja(); S.q = ""; ir("vender"); },
    verVentaDia: (v) => abrirVentaDia(Number(v)),
    filtroProd: (v) => { S.filtroProd = v; pantallaProductos(); },
    editPrecio: (v) => {
      const i = S.cart.find((x) => x.id === Number(v)); if (!i) return;
      S.editPrecio = i.id; S.precioEdit = i.precioFinal != null ? f2.format(i.precioFinal) : "";
      renderHoja(); setTimeout(() => { const el = $("#inPrecio"); if (el) el.focus(); }, 60);
    },
    cancelPrecio: () => { S.editPrecio = null; renderHoja(); },
    quitarDesc: (v) => { const i = S.cart.find((x) => x.id === Number(v)); if (i) i.precioFinal = null;
      S.editPrecio = null; S.pagos = []; renderHoja(); renderTotalbar(); },
    guardarPrecio: (v) => {
      const i = S.cart.find((x) => x.id === Number(v)); if (!i) return;
      const valor = parseMonto(S.precioEdit);
      if (!(valor > 0)) return toast("Escribe el precio que le vas a cobrar", true);
      if (valor > i.precio) return toast(`No puede ser mayor que el precio normal (${usd(i.precio)})`, true);
      const pct = (1 - valor / i.precio) * 100;
      if (pct > descMax() + 1e-9) return toast(`El descuento máximo permitido es ${f2.format(descMax())}%. Súbelo en Configuración.`, true);
      i.precioFinal = pct < 0.005 ? null : valor;
      S.editPrecio = null; S.pagos = [];
      toast(i.precioFinal != null ? `Precio ajustado a ${usd(valor)}` : "Precio normal");
      renderHoja(); renderTotalbar();
    },
    compartirPrecio: () => {
      const p = prod(S.prodSel); if (!p) return;
      const ivaPct = Number(S.cfg.iva_porcentaje || 16);
      const L = [`*${S.cfg.empresa_nombre || "SERVICIOS AUTOS LED"}*`, "", p.nombre, `Código: ${p.sku}`,
        `Precio: *${usd(p.precio)}* (${bs(r2(p.precio * S.tasa))} a tasa BCV ${f4.format(S.tasa)})`];
      if (!p.exento) L.push(`Con IVA ${ivaPct}%: ${usd(r2(p.precio * (1 + ivaPct / 100)))}`);
      L.push(p.servicio ? "Servicio disponible ✅" : p.stock > 0 ? "Disponible ✅" : "Agotado por el momento");
      abrirWhatsApp(L.join("\n"), "");
    },
    nuevoProd: (v) => {
      const q = (S.q || "").trim();
      const pareceCodigo = /^[A-Za-z0-9-]+$/.test(q) && /\d/.test(q);
      abrirNuevo(v === "busqueda" ? (pareceCodigo ? { sku: q } : { nombre: q }) : {});
    },
    nvAutoSku: () => { S.nuevo.autoSku = !S.nuevo.autoSku; renderHoja(); },
    nvExento: () => { S.nuevo.exento = !S.nuevo.exento; renderHoja(); },
    nvGuardar: () => guardarNuevo(),
  };

  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-a]");
    if (!b || b.disabled) return;
    const fn = ACC[b.dataset.a];
    if (fn) { e.preventDefault(); fn(b.dataset.v, b); }
  });
  sheetEl.addEventListener("click", (e) => { if (e.target === sheetEl) cerrarHoja(); });
  document.addEventListener("input", (e) => {
    const t = e.target;
    if (t.id === "q") { S.q = t.value; renderLista(); return; }
    const f = t.dataset && t.dataset.f;
    if (["tipo", "numero", "nombre", "telefono"].includes(f)) S.cliente[f] = t.value;
    else if (f === "ref") S.pagoRef = t.value;
    else if (f === "monto") S.pagoMonto = t.value;
    else if (f === "precioFinal") {
      S.precioEdit = t.value;
      const i = S.cart.find((x) => x.id === S.editPrecio);
      if (i && $("#infoDesc")) $("#infoDesc").innerHTML = infoDescuento(i, parseMonto(t.value));
    }
    else if (f && f.startsWith("nv_") && S.nuevo) {
      S.nuevo[f.slice(3)] = t.value;
      if ((f === "nv_precio" || f === "nv_costo") && $("#nvInfo"))
        $("#nvInfo").innerHTML = infoPrecio(parseMonto(S.nuevo.precio), parseMonto(S.nuevo.costo));
    }
  });
  document.addEventListener("change", (e) => {
    const t = e.target;
    if (t.dataset && (t.dataset.f === "numero" || t.dataset.f === "tipo")) { S.cliente[t.dataset.f] = t.value; buscarCliente(); }
    if (t.id === "fechaVentas" && t.value) { S.fechaVentas = t.value; $("#ventasDia").innerHTML = `<p class="sub">Cargando…</p>`; cargarVentasDia(); }
  });
  document.addEventListener("keydown", (e) => {
    // Lector de código por Enter: si lo escrito es un código exacto, se agrega directo
    if (e.key === "Enter" && e.target.id === "q" && S.tab === "vender") {
      const p = S.productos.find((x) => x.sku.toUpperCase() === e.target.value.trim().toUpperCase());
      if (p && agregar(p.id)) { S.q = ""; e.target.value = ""; renderLista(); }
      e.target.blur();
    }
    if (e.key === "Escape" && S.hoja) cerrarHoja();
  });
  window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); instalarEvt = e; if (S.tab === "inicio" && $("#main")) pantallaInicio(); });
  // Al volver a la app después de un rato, refrescar tasa y stock
  document.addEventListener("visibilitychange", async () => {
    if (document.visibilityState !== "visible" || !S.user || S.hoja) return;
    try { await cargarBase(); shell(); ir(S.tab); } catch (e) { /* sin conexión: se mantiene lo cargado */ }
  });
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});

  // ------------------------------------------------------------------ arranque
  (async () => {
    const { data } = await sb.auth.getSession();
    if (data && data.session) { S.user = data.session.user; iniciar(); }
    else pantallaLogin();
  })();
})();
