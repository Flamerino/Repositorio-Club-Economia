"""Sube a Supabase todo lo que haya en data/processed/<fuente>/series.csv + observaciones.csv.

Uso:
    python src/cargar_supabase.py            # todas las fuentes
    python src/cargar_supabase.py bcra       # solo una
    python src/cargar_supabase.py --dry-run  # muestra qué subiría, sin conectarse
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
RAIZ = Path(__file__).resolve().parents[1]
# Carpetas que están en el repo pero NO se suben a la base (y por lo tanto no aparecen en la página)
# salvo que se pidan explícitamente por nombre: python src/cargar_supabase.py datos_gob
SOLO_REPO = {"datos_gob"}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    carpetas = [RAIZ / "data" / "processed" / f for f in args] if args else \
        [p.parent for p in (RAIZ / "data" / "processed").glob("*/series.csv") if p.parent.name not in SOLO_REPO]

    for carpeta in carpetas:
        series = pd.read_csv(carpeta / "series.csv")
        if "id_api_bcra" in series:
            series["id_api_bcra"] = series["id_api_bcra"].astype("Int64").astype(object)
            series.loc[series["id_api_bcra"].isna(), "id_api_bcra"] = None
        obs = pd.read_csv(carpeta / "observaciones.csv")
        print(f"[{carpeta.name}] {len(series)} series, {len(obs):,} observaciones")
        if dry:
            continue
        from supabase_db import upsert
        upsert("series", series.to_dict("records"), "id")
        upsert("observaciones", obs.to_dict("records"), "serie_id,fecha")
        print(f"[{carpeta.name}] cargado")


if __name__ == "__main__":
    main()
