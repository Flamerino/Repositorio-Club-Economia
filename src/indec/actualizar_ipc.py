"""Actualiza el IPC nivel general (INDEC) desde la API de Series de Tiempo de datos.gob.ar.

Serie 148.3_INIVELNAL_DICI_M_26: IPC nacional, nivel general, base dic-2016=100 (la misma
que trae el archivo de INDEC). Antes de cargar, compara los meses que ya están en la base:
si no coinciden, no carga nada y deja un aviso.

Uso: python src/indec/actualizar_ipc.py
"""
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from supabase_db import aviso, leer_serie, upsert  # noqa: E402

API = "https://apis.datos.gob.ar/series/api/series/"
ID_API = "148.3_INIVELNAL_DICI_M_26"
SERIE = "indec_ipc_nivel_general"
TOLERANCIA = 0.001  # 0,1% de diferencia relativa máxima en los meses ya cargados


def traer():
    r = requests.get(API, params={"ids": ID_API, "format": "json", "limit": 5000}, timeout=60)
    r.raise_for_status()
    return {fila[0][:10]: fila[1] for fila in r.json()["data"] if fila[1] is not None}


def validar(nuevos, actuales):
    comunes = [f for f in actuales if f in nuevos]
    if len(comunes) < 12:
        return f"solo {len(comunes)} meses en común con la base"
    peor = max(abs(nuevos[f] / actuales[f] - 1) for f in comunes)
    if peor > TOLERANCIA:
        return f"diferencia de {peor:.2%} con los datos ya cargados"
    return None


def main():
    try:
        nuevos = traer()
    except Exception as e:  # noqa: BLE001
        aviso(f"IPC: no se pudo consultar la API de datos.gob.ar ({e}). Se mantiene el dato anterior.")
        return
    actuales = {f["fecha"]: f["valor"] for f in leer_serie(SERIE)}
    problema = validar(nuevos, actuales)
    if problema:
        aviso(f"IPC: la API no coincide con la base ({problema}). No se cargó nada.")
        return
    a_cargar = [{"serie_id": SERIE, "fecha": f, "valor": v} for f, v in nuevos.items()
                if f not in actuales or abs(v / actuales[f] - 1) > 1e-9]
    if a_cargar:
        upsert("observaciones", a_cargar, "serie_id,fecha")
    print(f"IPC: {len(a_cargar)} meses nuevos o corregidos. Último dato: {max(nuevos)}.")


if __name__ == "__main__":
    main()
