# Cómo contribuir

## Reportar un problema

Si un dato no coincide con la fuente o una serie dejó de actualizarse, abrir un *issue* con la serie (su `id` figura en [`datos/INDICE.csv`](datos/INDICE.csv)), la fecha y el valor esperado con su fuente.

## Sumar una serie de datos.gob.ar

Agregar una entrada en [`src/datos_gob/catalogo.py`](src/datos_gob/catalogo.py):

```python
dict(sid="indec_nueva_serie", nombre="Nombre legible", categoria="Actividad", unidad="Índice", freq="M", dias=110,
     id="ID_EN_LA_API", q="texto para buscarla si el ID cambia", kw=["palabras", "que deben", "aparecer"],
     fuente="INDEC"),
```

No hace falta tocar nada más: se descarga, se valida y aparece en `datos/` en la próxima corrida.

## Sumar una fuente nueva

1. Crear `src/<fuente>/actualizar.py`, que escriba `data/processed/<fuente>/series.csv` y `observaciones.csv` con las mismas columnas que el resto. Es el área de trabajo de la corrida: el exportador las publica en `datos/`, un archivo por serie. Para leer series ya publicadas, usar `src/almacen.py`.
2. **Validar antes de guardar:** comparar contra un dato conocido (otra fuente oficial, una cifra publicada o la historia ya guardada). Si no coincide, no escribir nada y emitir un aviso (`print("::warning::…")`).
3. Agregar `<fuente>` a `SOLO_REPO` en [`src/almacen.py`](src/almacen.py) mientras no se quiera mostrar en la página.
4. Agregar el script a `FUENTES` en [`src/actualizar_solo_repo.py`](src/actualizar_solo_repo.py), con las carpetas de `data/raw/` que escribe.
5. Documentar la fuente en [`docs/FUENTES.md`](docs/FUENTES.md) y, si es un cálculo propio, en [`docs/METODOLOGIA.md`](docs/METODOLOGIA.md).

## Convenciones

- **IDs:** prefijo de la fuente y nombre descriptivo en minúsculas (`bcra_…`, `indec_…`, `club_…` para elaboración propia).
- **Nombres:** completos y en castellano; la unidad va en su columna, no en el nombre.
- **Fechas:** primer día del período (ver [metodología](docs/METODOLOGIA.md)).
- **Descripción:** toda serie propia explica cómo se calcula y de qué fuentes sale.
- **Fuentes no oficiales:** se identifican como tales en el campo `fuente`.
