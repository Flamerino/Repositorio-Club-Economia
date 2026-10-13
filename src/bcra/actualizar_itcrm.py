"""Descarga la última versión de ITCRMSerie.xlsx del BCRA y actualiza el ITCRM y los
tipos de cambio bilaterales. Antes de cargar compara la historia con la base: si no
coincide (archivo distinto, cambio de formato), no carga nada y deja un aviso.

Uso: python src/bcra/actualizar_itcrm.py
"""
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import limpiar  # noqa: E402
from supabase_db import aviso, leer_serie, upsert  # noqa: E402

URLS = [  # el BCRA movió sus archivos a /archivos/ en 2026; se prueba la ruta nueva y la vieja
    "https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/ITCRMSerie.xlsx",
    "https://www.bcra.gob.ar/Pdfs/PublicacionesEstadisticas/ITCRMSerie.xlsx",
]
DESTINO = limpiar.RAW / "tipo_de_cambio" / "ITCRMSerie.xlsx"
TOLERANCIA = 0.01  # 1%: el BCRA revisa los últimos meses, se compara la historia más vieja


def descargar():
    for url in URLS:
        try:
            r = requests.get(url, timeout=120, headers={"User-Agent": "Mozilla/5.0"})
        except requests.RequestException:
            continue
        if r.ok and r.content[:2] == b"PK":  # un .xlsx es un zip; descarta páginas de error
            return r.content
    return None


def validar(obs):
    nuevo = obs[obs["serie_id"] == "bcra_itcrm"].set_index("fecha")["valor"]
    actual = pd.Series({pd.Timestamp(f["fecha"]): f["valor"] for f in leer_serie("bcra_itcrm")})
    corte = actual.index.max() - pd.DateOffset(months=6)  # historia que ya no se revisa
    comunes = actual.index[actual.index <= corte].intersection(nuevo.index)
    if len(comunes) < 1000:
        return f"solo {len(comunes)} días en común con la base"
    dif = (nuevo[comunes] / actual[comunes] - 1).abs().median()
    if dif > TOLERANCIA:
        return f"diferencia mediana de {dif:.2%} con la historia cargada"
    return None


def main():
    contenido = descargar()
    if contenido is None:
        aviso("ITCRM: no se pudo descargar ITCRMSerie.xlsx del BCRA. Se mantiene el dato anterior.")
        return
    anterior = DESTINO.read_bytes() if DESTINO.exists() else None
    DESTINO.write_bytes(contenido)
    try:
        metas, obs = limpiar.itcrm()
        obs = pd.concat(obs, ignore_index=True)
        problema = validar(obs)
    except Exception as e:  # noqa: BLE001
        problema = f"no se pudo leer el archivo ({e})"
    if problema:
        if anterior is not None:
            DESTINO.write_bytes(anterior)
        aviso(f"ITCRM: el archivo nuevo no coincide con la base ({problema}). No se cargó nada.")
        return
    upsert("series", metas, "id")
    obs["fecha"] = obs["fecha"].dt.strftime("%Y-%m-%d")
    upsert("observaciones", obs.to_dict("records"), "serie_id,fecha")
    print(f"ITCRM: {len(metas)} series actualizadas. Último dato: {obs['fecha'].max()}.")


if __name__ == "__main__":
    main()
