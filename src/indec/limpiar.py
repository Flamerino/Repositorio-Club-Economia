"""Limpia el IPC de INDEC (cobertura nacional, base dic-2016=100).

Genera data/processed/indec/series.csv y observaciones.csv
Uso: python src/indec/limpiar.py
"""
import re
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
ARCHIVO = next((RAIZ / "data" / "raw" / "indec" / "ipc").glob("sh_ipc_[0-9]*.xls"))
SALIDA = RAIZ / "data" / "processed" / "indec"


def slug(txt):
    txt = txt.lower().translate(str.maketrans("áéíóúñ", "aeioun"))
    return re.sub(r"[^a-z0-9]+", "_", txt).strip("_")


def main():
    d = pd.read_excel(ARCHIVO, sheet_name="Índices IPC Cobertura Nacional", header=None)
    fila_fechas = d.index[d[0].astype(str).str.strip() == "Total nacional"][0]
    fin = d.index[(d.index > fila_fechas) & d[0].astype(str).str.startswith("Región")][0]
    fechas = pd.to_datetime(d.iloc[fila_fechas, 1:], errors="coerce")

    metas, obs = [], []
    for i in range(fila_fechas + 1, fin):
        nombre = str(d.iloc[i, 0]).strip()
        valores = pd.to_numeric(d.iloc[i, 1:], errors="coerce")
        if nombre in ("nan", "") or valores.notna().sum() == 0:
            continue
        sid = f"indec_ipc_{slug(nombre)}"
        grupo = ("Categorías" if nombre in ("Estacional", "Núcleo", "Regulados") else
                 "Bienes y servicios" if nombre in ("Bienes", "Servicios") else "Divisiones")
        metas.append({"id": sid, "nombre": f"IPC {nombre} (Total nacional, dic-2016=100)",
                      "fuente": "INDEC", "categoria": "Precios", "unidad": "Índice", "frecuencia": "M",
                      "id_api_bcra": None, "archivo_origen": f"indec/ipc/{ARCHIVO.name}",
                      "descripcion": f"Índice de precios al consumidor, cobertura nacional. {grupo}: {nombre}."})
        o = pd.DataFrame({"serie_id": sid, "fecha": fechas.values, "valor": valores.values}).dropna()
        obs.append(o)

    SALIDA.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(metas).astype({"id_api_bcra": "Int64"}).to_csv(SALIDA / "series.csv", index=False)
    obs = pd.concat(obs, ignore_index=True)
    obs["fecha"] = pd.to_datetime(obs["fecha"]).dt.strftime("%Y-%m-%d")
    obs.to_csv(SALIDA / "observaciones.csv", index=False)
    print(f"-> {len(metas)} series de IPC, {len(obs):,} observaciones "
          f"({obs.fecha.min()} a {obs.fecha.max()})")


if __name__ == "__main__":
    main()
