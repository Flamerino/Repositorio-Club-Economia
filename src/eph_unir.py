"""Descarga bases trimestrales de la EPH (INDEC) y las une en un solo archivo.

Uso:
    python src/eph_unir.py --desde 2020 --hasta 2021
    python src/eph_unir.py --desde 2017 --hasta 2024 --tipo individual

Genera data/processed/eph/eph_<tipo>_<desde>_<hasta>.parquet
Fuente: microdatos de la EPH, vía el espejo de datos de pyeph (reflejar/pyeph-data).
"""
import argparse
import io
import zipfile
from pathlib import Path

import pandas as pd
import requests

URL = "https://raw.githubusercontent.com/reflejar/pyeph-data/master/{tipo}/base_{tipo}_{anio}T{trim}.zip"
RAIZ = Path(__file__).resolve().parents[1]


def bajar_trimestre(tipo, anio, trim):
    r = requests.get(URL.format(tipo=tipo, anio=anio, trim=trim), timeout=120)
    if r.status_code != 200:
        print(f"[no disponible] {tipo} {anio}T{trim}")
        return None
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        df = pd.read_csv(z.open(z.namelist()[0]), low_memory=False)
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]  # columnas vacías de algunos trimestres
    print(f"[ok] {tipo} {anio}T{trim}: {len(df):,} filas")
    return df


def normalizar_tipos(df):
    """Unifica tipos entre trimestres: algunos vienen como texto (con coma decimal o espacios)."""
    for c in df.columns[df.dtypes == object]:
        txt = df[c].astype("string").str.strip().replace("", pd.NA)
        num = pd.to_numeric(txt.str.replace(",", ".", regex=False), errors="coerce")
        if num.notna().sum() == txt.notna().sum():  # todo convertible -> numérica
            df[c] = num
        else:
            df[c] = txt
    return df


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--desde", type=int, required=True)
    p.add_argument("--hasta", type=int, required=True)
    p.add_argument("--tipo", choices=["individual", "hogar", "ambas"], default="ambas")
    args = p.parse_args()

    tipos = ["individual", "hogar"] if args.tipo == "ambas" else [args.tipo]
    salida = RAIZ / "data" / "processed" / "eph"
    salida.mkdir(parents=True, exist_ok=True)

    for tipo in tipos:
        partes = [bajar_trimestre(tipo, a, t)
                  for a in range(args.desde, args.hasta + 1) for t in range(1, 5)]
        partes = [d for d in partes if d is not None]
        if not partes:
            continue
        df = normalizar_tipos(pd.concat(partes, ignore_index=True))
        destino = salida / f"eph_{tipo}_{args.desde}_{args.hasta}.parquet"
        df.to_parquet(destino, index=False)
        print(f"-> {destino.relative_to(RAIZ)} ({len(df):,} filas, {df.shape[1]} columnas)")


if __name__ == "__main__":
    main()
