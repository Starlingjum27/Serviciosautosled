# Servicios Autos LED · Sistema de inventario y ventas

Sistema para un local de autopartes en Venezuela: punto de venta, compras, inventario (kardex),
proveedores y tasa BCV. Emite documentos **no fiscales** (notas de entrega / comprobantes internos).

Todo el sistema está en este repositorio:

| Parte | Carpeta | Dónde está publicada | Tecnología |
|---|---|---|---|
| Sistema principal (PC) | raíz: `streamlit_app.py`, `app/` | https://serviciosautosled.streamlit.app | Python + Streamlit |
| App móvil (celular) | `movil/` | https://autosled.netlify.app | HTML/JS (PWA instalable) |
| Base de datos | `supabase/` | Supabase (PostgreSQL) | Tablas, funciones SQL y RLS |

Las dos apps usan **la misma base de datos** y **las mismas funciones SQL** (`registrar_venta`,
`registrar_compra`, `anular_venta`, `anular_compra`, `tasa_vigente`), así que los cierres de caja cuadran.

## Estructura

```
streamlit_app.py          Entrada: login, menú y navegación
app/
  db.py                   Conexión a Supabase (un cliente por sesión)
  utils.py                Formatos VE, tasa vigente, cálculo de IVA/IGTF (espejo del SQL)
  sidebar.py              Barra lateral
  comprobante.py          Comprobantes de venta y compra (HTML imprimible)
  assets/                 Logos e ícono
  modules/
    dashboard.py  ventas.py  compras.py  productos.py
    proveedores.py  kardex.py  tasa_bcv.py  configuracion.py
movil/                    App móvil (Inicio · Vender · Productos · Ventas)
  config.example.js       Plantilla → copiar como config.js (no se sube a GitHub)
supabase/
  exportar_esquema.sql    Script para sacar el esquema de Supabase
  schema.sql              Esquema exportado (tablas, funciones, triggers, RLS)
netlify.toml              Configuración de publicación de movil/ en Netlify
.streamlit/secrets.toml.example   Plantilla de secretos de Streamlit
```

## Correr el sistema en tu PC

```bash
pip install -r requirements.txt
```

```bash
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
```

Edita `.streamlit/secrets.toml` con la URL y la anon key de Supabase, y luego:

```bash
streamlit run streamlit_app.py
```

Para la app móvil: copia `movil/config.example.js` como `movil/config.js`, pon los mismos valores
y abre `movil/index.html` con un servidor local (por ejemplo `python -m http.server` dentro de `movil/`).

## Publicar cambios

**Ya no subas archivos por la web de GitHub ni descargues zips de "actualización".** Trabaja en esta
carpeta con Git:

```bash
git add -A
git commit -m "Describe el cambio"
git push
```

- **Streamlit Cloud** se actualiza solo con cada `git push` a `main`.
- **Netlify (móvil)**, dos opciones (ver `netlify.toml`):
  - *Arrastrar y soltar*: arrastra la carpeta `movil/` (con tu `config.js`) en Netlify → Deploys.
  - *Automático*: conecta el sitio a este repositorio y crea las variables `SUPABASE_URL` y
    `SUPABASE_ANON_KEY` en Netlify. Se publica solo en cada push.
  - Si cambias `app.js` o `styles.css`, sube la versión del caché en `movil/sw.js`
    (`autosled-v3` → `autosled-v4`) para que los celulares tomen la versión nueva.

## Base de datos (Supabase)

Las funciones SQL y las reglas de seguridad **no estaban guardadas en ningún lado**: solo vivían en
Supabase. Para respaldarlas:

1. Supabase → **SQL Editor** → pega `supabase/exportar_esquema.sql` → **Run**.
2. Copia la celda `esquema` del resultado y pégala en `supabase/schema.sql`.
3. `git commit` del archivo.

Repite el paso cada vez que cambies una tabla, función o política en Supabase.

> ⚠️ El plan gratis de Supabase **no hace respaldos de datos** y pausa el proyecto tras 7 días sin uso.
> Respalda los datos con regularidad (Table Editor → Export to CSV, o un script de respaldo).

## Claves y seguridad

- En el código solo se usa la **anon key** (pública). La **service_role** nunca debe ir en este
  repositorio, ni en `config.js` ni en Streamlit.
- La app móvil expone la anon key en el navegador (es normal), por eso **la seguridad real la dan las
  políticas RLS** de Supabase: cada tabla debe tener RLS activado y permitir acceso solo a usuarios
  autenticados.
- `.streamlit/secrets.toml` y `movil/config.js` están en `.gitignore`.
