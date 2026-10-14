# Repositorio de datos — Club de Economía UADE

Repositorio de series de tiempo de la economía argentina para el área de **policy and public impact** del Club de Economía. La idea es tener en un solo lugar las fuentes oficiales, ordenadas y reproducibles, para calcular fluctuaciones y usarlas como base de análisis.

## Estructura

```
data/
  catalogo_fuentes.csv   # qué archivo es, de dónde viene y dónde se guarda
  raw/                   # datos crudos, tal como los publica cada fuente
    indec/
      ipc/
      actividad_economica/
    banco_mundial/
    bcra/
      tipo_de_cambio/
      mercado_de_cambios/
      reservas/
      monetario/
      sistema_financiero/
      base_series/       # es_series.txt (diccionario) + tasa_ser.zip (valores)
    mecon/deuda_publica/
    opc/
  processed/             # series limpias listas para análisis
    eph/                 # EPH unida por trimestres (parquet)
app/                     # página web (Streamlit)
db/schema.sql            # tablas de la base (Supabase)
notebooks/               # análisis exploratorios
src/                     # scripts (descarga, limpieza, cálculos)
  bcra/limpiar.py        # archivos BCRA -> formato de la base
  bcra/actualizar_api.py # datos nuevos desde la API del BCRA
  cargar_supabase.py     # sube data/processed/*/ a Supabase
.github/workflows/       # actualización automática semanal
```

## Cómo empezar

Los datos crudos están en `data/raw/`, organizados por institución y tema. El catálogo (`data/catalogo_fuentes.csv`) indica de dónde sale cada archivo.

```bash
pip install -r requirements.txt
```

`tasa_ser.txt` pesa 169 MB (supera el límite de GitHub), por eso está comprimido como `data/raw/bcra/base_series/tasa_ser.zip`. Sus códigos de serie se buscan en `es_series.txt`.

`src/descargar_datos.py` permite volver a bajar los archivos desde el Drive del Club (por ejemplo, para actualizar series).

## Base de datos (Supabase)

Todas las fuentes se llevan al mismo formato y se cargan en dos tablas:

- `series`: una fila por serie (nombre, fuente, categoría, unidad, frecuencia, ID en la API del BCRA si tiene).
- `observaciones`: `serie_id`, `fecha`, `valor`.

Flujo: **archivo crudo o API → `src/<fuente>/limpiar.py` → `data/processed/<fuente>/` → `cargar_supabase.py` → Supabase → página**.

### BCRA (171 series)

- 154 series de `SerieReservas.xlsm` (reservas, base monetaria, depósitos, préstamos, tasas, instrumentos del BCRA), diarias desde 2003. Cada una tiene su `IdVariable` de la API del BCRA, así que se actualizan solas todas las semanas.
- 15 series de tipo de cambio real (ITCRM y bilaterales), diarias desde 1997.
- 2 series de bandas cambiarias (incluye las fechas futuras ya anunciadas).

ITCRM y bandas no están en la API: se actualizan reemplazando el archivo en `data/raw/bcra/tipo_de_cambio/` y corriendo una carga completa.

### Puesta en marcha (una sola vez)

1. Crear un proyecto en [supabase.com](https://supabase.com) → **SQL Editor** → pegar `db/schema.sql` → **Run**.
2. En Supabase, **Project Settings → API**: copiar la **Project URL** y la clave **service_role**.
3. En GitHub, **Settings → Secrets and variables → Actions → New repository secret**: crear `SUPABASE_URL` y `SUPABASE_SERVICE_KEY` con esos valores.
4. En GitHub, **Actions → Actualizar datos → Run workflow**, tildando *carga completa*. Carga toda la historia y después actualiza por API.

Desde ahí corre solo todos los lunes. La clave service_role nunca va en el código ni en la página: la página usa la clave **anon**, que solo permite leer.

## Series de elaboración propia

`src/derivadas/calcular.py` construye series cruzando las de la base (categoría *Elaboración propia*, ids con prefijo `club_`). Cada una tiene su metodología en la columna `descripcion`:

| Serie | Qué responde |
|---|---|
| `club_tasa_real_badlar` | ¿Le gana el plazo fijo a la inflación? (tasa real ex post) |
| `club_itcrm_desvio` | ¿Está el peso apreciado o depreciado respecto de su promedio histórico? (referencia, no equilibrio) |
| `club_dolarizacion_depositos`, `club_prestamos_depositos` | Dolarización y profundidad del crédito |
| `club_base_real`, `club_m2_real`, `club_prestamos_pesos_real` | Agregados monetarios y crédito en términos reales |

Se recalculan solas cada lunes, después de la actualización por API. Para sumar una, agregarla en `calcular()` con su `descripcion`.

Se dieron de baja `club_respaldo_base`, `club_tc_convertibilidad` (usaban reservas brutas, que sobreestiman el respaldo) y `club_carry_usd` (medido al dólar oficial, no era replicable con cepo). Están en la lista `RETIRADAS` de `calcular.py`, que las borra de la base en cada corrida.

## Actualización automática (todos los lunes)

| Paso | Qué actualiza | Fuente |
|---|---|---|
| `src/bcra/actualizar_api.py` | 154 series del BCRA (reservas, base, depósitos, préstamos, tasas) | API Estadísticas Monetarias v4.0 |
| `src/indec/actualizar_ipc.py` | IPC nivel general | API Series de Tiempo (datos.gob.ar), id `148.3_INIVELNAL_DICI_M_26` |
| `src/bcra/actualizar_itcrm.py` | ITCRM y 14 tipos de cambio bilaterales | `ITCRMSerie.xlsx` del sitio del BCRA |
| `src/derivadas/calcular.py` | Las 7 series de elaboración propia | Base de datos |

IPC e ITCRM se **validan contra la historia ya cargada** antes de escribir: si no coinciden (otra serie, cambio de formato), no se carga nada y queda un aviso amarillo en el resumen de la corrida. `data/estado_actualizacion.json` registra la última fecha de cada fuente después de cada corrida.

Siguen manuales: las aperturas del IPC que se muestran en la página (las principales ya se actualizan solas en `data/processed/datos_gob/`) y las bandas cambiarias. Se actualizan reemplazando el archivo en `data/raw/` y corriendo una carga completa.

## Pobreza y precios relativos

`src/indec/pobreza.py` mide pobreza e indigencia con la metodología oficial de INDEC (ingreso total familiar contra CBT/CBA por adulto equivalente y región, EPH 31 aglomerados, ponderador `PONDIH`) y calcula cuánto de esa pobreza se explica por cambios en el precio relativo de la canasta.

**Validación contra INDEC (% de personas bajo la línea de pobreza):**

| Semestre | Club | INDEC | | Semestre | Club | INDEC |
|---|---|---|---|---|---|---|
| 1° 2017 | 28,5 | 28,6 | | 1° 2022 | 36,3 | 36,5 |
| 2° 2017 | 25,6 | 25,7 | | 2° 2022 | 39,4 | 39,2 |
| 1° 2018 | 27,3 | 27,3 | | 1° 2023 | 40,0 | 40,1 |
| 2° 2018 | 31,8 | 32,0 | | 2° 2023 | 41,9 | 41,7 |
| 1° 2019 | 35,3 | 35,4 | | 1° 2024 | 52,9 | 52,9 |
| 2° 2019 | 35,7 | 35,5 | | 2° 2024 | 38,1 | 38,1 |
| 1° 2020 | 40,8 | 40,9 | | 1° 2025 | 31,6 | 31,6 |
| 2° 2020 | 42,1 | 42,0 | | 2° 2025 | 28,4 | 28,2 |
| 1° 2021 | 40,4 | 40,6 | | 1° 2026 | — | 32,3 |
| 2° 2021 | 37,3 | 37,3 | | | | |

**Contrafactual:** misma medición con canastas que desde dic-2016 suben igual que el IPC nivel general. La diferencia con la pobreza medida es el efecto de que la canasta de los hogares pobres se encarezca más (o menos) que la inflación promedio. Mantiene fijos los ingresos.

**Vulnerabilidad:** reparte a la población en siete estratos según su ingreso familiar dividido su línea de pobreza (indigentes, pobres no indigentes, tres franjas de vulnerables hasta 1,5 líneas, 1,5–2 y más de 2). `club_vulnerables` = personas no pobres a menos de 50% de la línea.

**Sesgo por inflación:** la EPH releva los ingresos del mes anterior. `club_pobreza_alineada` repite la medición con la canasta de ese mismo mes; la diferencia (`club_sesgo_inflacion_pobreza`) crece casi linealmente con la inflación mensual (≈0,5 p.p. de pobreza por cada punto de inflación). Es un ejercicio de sensibilidad: supone que todos los ingresos son del mes anterior y trabaja con promedios trimestrales porque la base pública no trae el mes de entrevista.

**Datos y actualización.** EPH, canastas por región y adulto equivalente salen del espejo de [pyeph](https://github.com/reflejar/pyeph-data) y se guardan en `data/raw/indec/eph/` y `data/raw/indec/canastas/`. Como el espejo se actualiza con retraso, `pobreza.py` completa:

- **EPH:** los trimestres que el espejo no tiene se bajan directo de INDEC (`EPH_usu_<t>_Trim_<año>_txt.zip`).
- **Canasta de GBA:** se extiende mes a mes con `serie_cba_cbt.xls` de INDEC y con `data/raw/indec/canastas/cba_cbt_gba.csv` (valores oficiales cargados a mano; respaldo por si cambia el formato del xls). Antes de usarla se valida contra los meses en común con el espejo.
- **Canastas de las otras regiones:** INDEC las publica con el informe semestral. Mientras no estén, ese semestre no se calcula (no se estima nada).

Cada semestre hay que sumar una fila a `data/raw/indec/pobreza_oficial.csv` con la cifra oficial de INDEC. La página la muestra junto a la réplica del Club y avisa cuando INDEC ya publicó un semestre que la réplica todavía no tiene.

## Fuentes solo en el repo

Se actualizan solas cada lunes (`src/actualizar_solo_repo.py`) y se commitean en `data/processed/`, pero **no se suben a la base ni se muestran en la página**: cada carpeta tiene un archivo `.solo_repo`. Para publicar una, borrar ese archivo (o subirla a mano con `python src/cargar_supabase.py <carpeta>`).

| Carpeta | Fuente | Series | Control antes de guardar |
|---|---|---|---|
| `datos_gob/` | API Series de Tiempo (datos.gob.ar) | 30: EMAE, PIB trimestral, IPI, ISAC, índice de salarios (5), RIPTE, salario mínimo, haber mínimo, AUH, resultado primario y financiero, ingresos, gasto primario, intereses, exportaciones, importaciones, desocupación, informalidad, empleo registrado (SIPA), aperturas del IPC (núcleo, regulados, alimentos, vivienda), CBA y CBT | Metadatos de cada ID; historia contra lo guardado; frescura |
| `mercados/` | ArgentinaDatos (no oficial) | Dólar oficial, mayorista, blue, MEP, CCL, brechas y riesgo país (diarios) | Mayorista vs A3500 del BCRA (diferencia mediana histórica 0,08%) |
| `banco_mundial/` | API del Banco Mundial | 8 indicadores × 11 países (Argentina, región y mundo): crecimiento, inflación, PIB per cápita PPA, desempleo, Gini, inversión, exportaciones, deuda | Crecimiento de Argentina vs el archivo del Banco Mundial en `data/raw/` |

Si una fuente no responde o no pasa el control, se conservan sus datos anteriores y queda un aviso amarillo en la corrida.

### Cómo sumar una fuente nueva

1. **Una serie más de datos.gob.ar:** agregar una línea en `src/datos_gob/catalogo.py` (ID, palabras clave que deben aparecer en su descripción, frecuencia, días máximos sin datos). Nada más.
2. **Una fuente distinta:** crear `src/<fuente>/actualizar.py` que escriba `data/processed/<fuente>/series.csv` y `observaciones.csv`, con algún control contra un dato conocido antes de guardar; crear `data/processed/<fuente>/.solo_repo`; y sumar el script a `FUENTES` en `src/actualizar_solo_repo.py`. El workflow no se toca.

### Detalles de datos.gob.ar

- **ID verificado:** los metadatos que devuelve la API tienen que contener las palabras clave de la serie; si no, busca por texto y solo acepta si hay un único candidato. Si hay varios, deja un aviso con la lista para fijar el ID a mano.
- **Índice de salarios:** fuente principal el CSV del INDEC (`indice_salarios.csv`, URL fija); la API es respaldo porque llegó a estar meses sin actualizarse.
- **Salario mínimo y haber mínimo:** recortados desde 1992 (antes están en australes y otras monedas). El salario mínimo incluye meses futuros ya fijados por decreto.

## Página web (Streamlit)

`app/app.py` es la página del Club: lee de Supabase con la clave pública (solo lectura).

- **Resumen:** indicadores clave con su variación en 30 días y los últimos 2 años.
- **Pobreza y precios:** canastas básicas y rubros del IPC en términos reales, pobreza e indigencia medidas y contrafactuales.
- **Análisis:** las series de elaboración propia, cada una con una pregunta, el gráfico y una lectura que se recalcula con el último dato.
- **Explorar series:** elegir series por categoría, período, frecuencia (original, promedio mensual, fin de mes) y transformación (nivel, variación mensual, interanual, base 100). Tabla y descarga en CSV.
- **Sobre los datos:** catálogo completo.

Solo se ejecuta la sección elegida y las series de cada sección se bajan en paralelo, para que la primera carga no tarde.

Correrla en la compu:

```bash
pip install -r app/requirements.txt
streamlit run app/app.py
# sin internet, con los CSV de data/processed/:
DATOS_LOCALES=1 streamlit run app/app.py
```

Para sumar una serie al resumen, agregar su `id` a la lista `RESUMEN` al principio de `app/app.py`.

## EPH (microdatos)

`data/processed/eph/` tiene las bases de la EPH 2020 T1 – 2021 T4 unidas en un solo archivo por tipo:

- `eph_individual_2020_2021.parquet`: 366.827 personas, 177 variables
- `eph_hogar_2020_2021.parquet`: 121.131 hogares, 88 variables

Cada fila conserva `ANO4` y `TRIMESTRE`, así que se puede filtrar o agrupar por período. Para sumar otros años:

```bash
python src/eph_unir.py --desde 2017 --hasta 2024
```

```python
import pandas as pd
ind = pd.read_parquet("data/processed/eph/eph_individual_2020_2021.parquet")
```

## Fuentes

| Institución | Temas |
|---|---|
| INDEC | IPC, oferta y demanda globales, VBP y VAB |
| BCRA | Tipo de cambio real, bandas cambiarias, balance cambiario, reservas, información monetaria, sistema financiero, tasas |
| Ministerio de Economía (MECON) | Deuda pública |
| Oficina de Presupuesto del Congreso (OPC) | Recaudación tributaria |
| Banco Mundial | Crecimiento del PIB (NY.GDP.MKTP.KD.ZG) |

### Fuentes por API / web (sin archivo)

- **BCRA — APIs:** https://www.bcra.gob.ar/apis-banco-central/
- **INDEC — EPH (empleo):** librería [`pyeph`](https://pypi.org/project/pyeph/)
- **INDEC — Anuario estadístico (economía):** https://anuario.indec.gob.ar/dominio02.html?menu=Econom%C3%ADa&dominio=Dominio%202
