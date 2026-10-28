"""Trae los datos nuevos de la API pública del BCRA (Estadísticas Monetarias v4.0)
para todas las series que tienen IdVariable, y los carga en Supabase.

Para cada serie pide desde 30 días antes de la última fecha cargada,
así también se capturan revisiones de datos recientes.

Uso:
    python src/bcra/actualizar_api.py
"""
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from supabase_db import aviso, ultima_fecha, upsert  # noqa: E402

API = "https://api.bcra.gob.ar/estadisticas/v4.0/monetarias/{id}"
RAIZ = Path(__file__).resolve().parents[2]


def pedir(id_api, params, intentos=4):
    """GET a la API con reintentos: la API del BCRA corta conexiones y devuelve 429/5xx de vez en cuando."""
    for i in range(intentos):
        try:
            r = requests.get(API.format(id=id_api), timeout=60, params=params)
            if r.status_code == 404 or (r.ok and r.status_code < 300):
                return r
            if r.status_code not in (429, 500, 502, 503, 504):
                r.raise_for_status()
        except (requests.ConnectionError, requests.Timeout):
            if i == intentos - 1:
                raise
        time.sleep(5 * (i + 1))
    r.raise_for_status()
    return r


def traer(id_api, desde):
    filas, offset = [], 0
    while True:
        r = pedir(id_api, {"desde": desde, "hasta": date.today().isoformat(), "limit": 3000, "offset": offset})
        if r.status_code == 404:
            return None
        r.raise_for_status()
        cuerpo = r.json()
        detalle = [d for res in cuerpo.get("results", []) for d in res.get("detalle", [])]
        filas += detalle
        total = cuerpo.get("metadata", {}).get("resultset", {}).get("count", len(filas))
        offset += 3000
        if not detalle or offset >= total:
            return filas


def main():
    from almacen import metas
    series = metas("bcra")  # de esta corrida o, si no corrió la carga completa, del índice publicado
    series = series.dropna(subset=["id_api_bcra"])
    total, sin_api, errores = 0, [], []

    for _, s in series.iterrows():
        sid, id_api = s["id"], int(s["id_api_bcra"])
        ult = ultima_fecha(sid)
        desde = (date.fromisoformat(ult) - timedelta(days=30)).isoformat() if ult else "2003-01-01"
        try:
            filas = traer(id_api, desde)
        except Exception as e:  # noqa: BLE001
            errores.append(f"{sid}: {e}")
            continue
        if filas is None:
            sin_api.append(sid)
            continue
        registros = [{"serie_id": sid, "fecha": f["fecha"], "valor": f["valor"]}
                     for f in filas if f.get("valor") is not None]
        if registros:
            total += upsert("observaciones", registros, "serie_id,fecha")
        time.sleep(0.3)  # no saturar la API

    print(f"Actualizadas {total:,} observaciones de {len(series)} series.")
    if sin_api:
        print(f"Sin datos en la API (series discontinuadas o ID cambiado): {', '.join(sin_api)}")
    if errores:
        print("Errores:\n  " + "\n  ".join(errores))
        # Unas pocas series con error no frenan el resto de la actualización (IPC, pobreza, etc.):
        # quedan como aviso y se reintentan la semana próxima. Solo se corta si falla la mayoría.
        if len(errores) > len(series) / 2:
            sys.exit(1)
        aviso(f"BCRA: {len(errores)} de {len(series)} series no se pudieron actualizar (ver log)")


if __name__ == "__main__":
    main()
