# Repositorio de datos — Club de Economía UADE

Repositorio de series de tiempo de la economía argentina para el área de **policy and public impact** del Club de Economía. La idea es tener en un solo lugar las fuentes oficiales, ordenadas y reproducibles, para calcular fluctuaciones y usarlas como base de análisis.

## Estructura

```
data/
  catalogo_fuentes.csv   # qué archivo es, de dónde viene y dónde se guarda
  raw/                   # datos crudos (no se suben a GitHub, se descargan)
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
      tasas/
    mecon/deuda_publica/
    opc/
  processed/             # series limpias listas para análisis
notebooks/               # análisis exploratorios
src/                     # scripts (descarga, limpieza, cálculos)
```

## Cómo empezar

```bash
pip install -r requirements.txt
python src/descargar_datos.py              # baja todo (~260 MB)
python src/descargar_datos.py --max-mb 50  # sin los archivos más pesados
```

Los datos crudos no se versionan: algunos superan el límite de GitHub y además se actualizan seguido. El catálogo (`data/catalogo_fuentes.csv`) es la referencia de qué hay y de dónde sale cada archivo.

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
