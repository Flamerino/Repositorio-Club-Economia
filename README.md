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

## Página web (Streamlit)

`app/app.py` es la página del Club: lee de Supabase con la clave pública (solo lectura).

- **Resumen:** indicadores clave con su variación en 30 días y los últimos 2 años.
- **Explorar series:** elegir series por categoría, período, frecuencia (original, promedio mensual, fin de mes) y transformación (nivel, variación mensual, interanual, base 100). Tabla y descarga en CSV.
- **Sobre los datos:** catálogo completo.

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
