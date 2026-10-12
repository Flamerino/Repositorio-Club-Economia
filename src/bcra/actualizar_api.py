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
from supabase_db import ultima_fecha, upsert  # noqa: E402

API = "https://api.bcra.gob.ar/estadisticas/v4.0/monetarias/{id}"
RAIZ = Path(__file__).resolve().parents[2]


def traer(id_api, desde):
    filas, offset = [], 0
    while True:
        r = requests.get(API.format(id=id_api), timeout=60,
                         params={"desde": desde, "hasta": date.today().isoformat(),
                                 "limit": 3000, "offset": offset})
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
    series = pd.read_csv(RAIZ / "data" / "processed" / "bcra" / "series.csv")
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
        sys.exit(1)


if __name__ == "__main__":
    main()
