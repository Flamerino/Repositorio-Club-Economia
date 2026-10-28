"""Acceso a las series ya publicadas del repositorio.

El repositorio guarda cada serie en su propio archivo dentro de datos/ (con datos/INDICE.csv como
catálogo). data/processed/ es un área de trabajo interna: los scripts escriben ahí durante la corrida
(series.csv + observaciones.csv por fuente) y no se versiona.

Para leer una serie, se usa lo que haya producido la corrida actual en data/processed/; si no está,
se lee la versión publicada en datos/.
"""
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
PROCESSED = RAIZ / "data" / "processed"
DATOS = RAIZ / "datos"
INDICE = DATOS / "INDICE.csv"

# Fuentes que se publican en datos/ pero no se suben a la base ni aparecen en la página.
# Para mostrar una en la página, sacarla de este conjunto.
SOLO_REPO = {"datos_gob", "mercados", "banco_mundial", "internacional", "opinion", "balance_cambiario", "rem",
             "distribucion"}
FREQ_CODIGO = {"Diaria": "D", "Mensual": "M", "Trimestral": "T", "Semestral": "S", "Anual": "A"}
COLUMNAS_META = ["id", "nombre", "fuente", "categoria", "unidad", "frecuencia", "id_api_bcra", "archivo_origen",
                 "descripcion"]


_CACHE = {}


def _leer(archivo):
    if archivo not in _CACHE:
        _CACHE[archivo] = pd.read_csv(archivo)
    return _CACHE[archivo]


def _indice():
    return pd.read_csv(INDICE) if INDICE.exists() else pd.DataFrame()


def metas(fuente):
    """Catálogo de una fuente (columnas de COLUMNAS_META)."""
    archivo = PROCESSED / fuente / "series.csv"
    if archivo.exists():
        return pd.read_csv(archivo)
    ind = _indice()
    if ind.empty or "carpeta_origen" not in ind:
        return pd.DataFrame(columns=COLUMNAS_META)
    ind = ind[ind["carpeta_origen"] == fuente]
    return pd.DataFrame({
        "id": ind["id"], "nombre": ind["serie"], "fuente": ind["fuente"], "categoria": ind["tema"],
        "unidad": ind["unidad"], "frecuencia": ind["frecuencia"].map(FREQ_CODIGO).fillna(ind["frecuencia"]),
        "id_api_bcra": ind.get("id_api_bcra"), "archivo_origen": ind.get("archivo_origen"),
        "descripcion": ind["descripcion"]})


def serie(serie_id, fuente=None):
    """DataFrame (fecha, valor) de una serie, o None si no existe."""
    carpetas = [PROCESSED / fuente] if fuente else sorted(p.parent for p in PROCESSED.glob("*/observaciones.csv"))
    for c in carpetas:
        archivo = c / "observaciones.csv"
        if archivo.exists():
            o = _leer(archivo)
            o = o[o["serie_id"] == serie_id]
            if len(o):
                return o[["fecha", "valor"]].reset_index(drop=True)
    ind = _indice()
    if not ind.empty:
        fila = ind[ind["id"] == serie_id]
        if len(fila) and (DATOS / fila["archivo"].iloc[0]).exists():
            return pd.read_csv(DATOS / fila["archivo"].iloc[0])
    return None


def observaciones(fuente):
    """Todas las observaciones de una fuente (serie_id, fecha, valor)."""
    archivo = PROCESSED / fuente / "observaciones.csv"
    if archivo.exists():
        return pd.read_csv(archivo)
    partes = []
    for sid in metas(fuente)["id"]:
        df = serie(sid)
        if df is not None:
            partes.append(df.assign(serie_id=sid)[["serie_id", "fecha", "valor"]])
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame(columns=["serie_id", "fecha", "valor"])
