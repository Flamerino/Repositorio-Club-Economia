# Arquitectura

```
Fuentes (APIs y archivos)
   │  src/<fuente>/…            descarga, validación, limpieza
   ▼
data/raw/ (originales)     data/processed/<fuente>/  (área de trabajo de la corrida, no se versiona)
                                        │
                     ┌──────────────────┴──────────────────────┐
                     ▼                                         ▼
          src/cargar_supabase.py                    src/exportar_archivos.py
                     ▼                                         ▼
          Supabase (base de datos) ──► app/ (página)     datos/ (un CSV por serie, versionado)
```

## Carpetas de datos

- **`data/raw/`**: archivos tal como los publica cada fuente (Excel del BCRA y del INDEC, microdatos de la EPH, canastas, etc.).
- **`datos/`**: la versión publicada de cada serie, un archivo por serie, generada por `src/exportar_archivos.py` en cada corrida. `datos/INDICE.csv` es el catálogo: nombre, fuente, unidad, frecuencia, período, descripción, origen exacto y si se muestra en la página. No se edita a mano.
- **`data/processed/<fuente>/`**: área de trabajo interna. Durante la corrida, cada script deja ahí sus series en formato largo (`series.csv` y `observaciones.csv`), que es el formato que usan la base y el exportador. No se versiona.

Cuando un script necesita datos ya publicados (para validar contra la historia o conservar una serie si su fuente falla), los lee con `src/almacen.py`: primero lo que produjo la corrida y, si no está, la versión de `datos/`. El exportador conserva las series que no se actualizaron en una corrida, así ninguna desaparece porque su fuente falle una semana.

Las fuentes listadas en `SOLO_REPO` (`src/almacen.py`) se publican en `datos/` pero no se suben a la base ni aparecen en la página. Para mostrar una en la página, se la saca de esa lista.

## Actualización semanal

`.github/workflows/actualizar_datos.yml` corre los lunes a las 9:00 (hora argentina) y también a mano desde **Actions → Actualizar datos → Run workflow**. Pasos:

1. **Carga completa** (solo si se tilda al lanzarlo a mano): limpia los archivos del BCRA y del INDEC y los sube a la base.
2. **BCRA por API:** actualiza las 154 series con `IdVariable`.
3. **IPC:** nivel general desde la API de datos.gob.ar.
4. **ITCRM:** archivo nuevo del BCRA.
5. **Pobreza e indigencia:** EPH y canastas.
6. **Fuentes complementarias:** `src/actualizar_solo_repo.py` corre cada fuente de su lista. Si una falla, avisa y sigue con las demás. Las que no están en `SOLO_REPO` se suben además a la base.
7. **Series de elaboración propia:** `src/derivadas/calcular.py`.
8. **`datos/`:** `src/exportar_archivos.py`. Si una lectura trae menos del 90% de las series que había, no modifica nada.
9. **Registro:** `src/estado.py` escribe `data/estado_actualizacion.json` y el workflow commitea los datos nuevos.

Un segundo workflow, `.github/workflows/mantener_base.yml`, hace una consulta mínima a la base todos los días: Supabase pausa los proyectos gratuitos tras 7 días sin actividad. Si la base no responde, la actualización se corta con un mensaje claro; en ese caso, restaurar el proyecto desde supabase.com.

Los avisos de cada corrida aparecen en amarillo en el resumen de la ejecución. Además, `data/raw/datos_gob/ESTADO.csv` y `data/raw/internacional/ESTADO.csv` detallan qué pasó con cada serie.

## Base de datos y página

La base es un proyecto de [Supabase](https://supabase.com) con dos tablas, definidas en [`db/schema.sql`](../db/schema.sql): `series` y `observaciones`. La lectura es pública; la escritura requiere la clave `service_role`, que solo usa GitHub Actions.

Puesta en marcha (una sola vez):

1. En Supabase: **SQL Editor** → pegar `db/schema.sql` y las migraciones de `db/migraciones/` → **Run**.
2. En GitHub: **Settings → Secrets and variables → Actions**, crear `SUPABASE_URL` y `SUPABASE_SERVICE_KEY`.
3. Correr el workflow con **carga completa**.

La página ([`app/`](../app/)) está publicada en Streamlit Community Cloud y lee la base con la clave pública. Para correrla localmente:

```bash
pip install -r app/requirements.txt
streamlit run app/app.py
DATOS_LOCALES=1 streamlit run app/app.py   # sin conexión, con los CSV de data/processed/
```

## Código (`src/`)

| Archivo | Función |
|---|---|
| `bcra/limpiar.py`, `bcra/actualizar_api.py`, `bcra/actualizar_itcrm.py` | Series del BCRA de la página |
| `bcra/balance_cambiario.py`, `bcra/rem.py` | Balance cambiario y REM |
| `indec/limpiar.py`, `indec/actualizar_ipc.py` | IPC |
| `indec/pobreza.py`, `indec/distribucion.py` | Pobreza, indigencia, vulnerabilidad y distribución del ingreso (EPH) |
| `datos_gob/catalogo.py`, `datos_gob/actualizar.py` | Series de la API de datos.gob.ar |
| `mercados/actualizar.py` | Dólares, brechas y riesgo país |
| `opinion/actualizar.py` | Índice de Confianza en el Gobierno |
| `banco_mundial/actualizar.py`, `internacional/actualizar.py` | Contexto internacional |
| `derivadas/calcular.py` | Series de elaboración propia |
| `actualizar_solo_repo.py` | Orquesta las fuentes complementarias y sube a la base las que van a la página |
| `almacen.py` | Lectura de series ya publicadas; lista de fuentes que no van a la página |
| `supabase_db.py`, `cargar_supabase.py` | Conexión y carga a la base |
| `exportar_archivos.py`, `estado.py` | Carpeta `datos/` y registro de la corrida |
