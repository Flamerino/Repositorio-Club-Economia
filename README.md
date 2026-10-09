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
notebooks/               # análisis exploratorios
src/                     # scripts (descarga, limpieza, cálculos)
```

## Cómo empezar

Los datos crudos están en `data/raw/`, organizados por institución y tema. El catálogo (`data/catalogo_fuentes.csv`) indica de dónde sale cada archivo.

```bash
pip install -r requirements.txt
```

`tasa_ser.txt` pesa 169 MB (supera el límite de GitHub), por eso está comprimido como `data/raw/bcra/base_series/tasa_ser.zip`. Sus códigos de serie se buscan en `es_series.txt`.

`src/descargar_datos.py` permite volver a bajar los archivos desde el Drive del Club (por ejemplo, para actualizar series).

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
