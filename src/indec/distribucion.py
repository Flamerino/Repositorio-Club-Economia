"""Distribución del ingreso (EPH, 31 aglomerados), por trimestre.

Ingreso per cápita familiar (IPCF) = ingreso total familiar / miembros del hogar; personas ponderadas
por PONDIH (excluye hogares sin respuesta de ingresos). Replica las cifras oficiales del INDEC:
Gini 0,467 (1T-2024), 0,436 (2T-2024), 0,424 (2T-2025); ingreso per cápita promedio $537.024 (2T-2025).

Usa la base de la EPH que arma src/indec/pobreza.py. Se publica en datos/ (no se sube a la base).
Uso: python src/indec/distribucion.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
EPH = RAIZ / "data" / "raw" / "indec" / "eph" / "eph_pobreza_2017_en_adelante.parquet"
SALIDA = RAIZ / "data" / "processed" / "distribucion"
FUENTE = "Club de Economía UADE (elaboración propia)"
CONTROL = {(2024, 1): 0.467, (2024, 2): 0.436, (2025, 2): 0.424}  # Gini oficial INDEC


def gini(x, w):
    o = np.argsort(x)
    x, w = x[o], w[o]
    cw, cxw = np.cumsum(w), np.cumsum(x * w)
    area = np.sum((cxw[1:] + cxw[:-1]) * np.diff(cw)) + cxw[0] * cw[0]
    return 1 - area / (cxw[-1] * cw[-1])


def main():
    if not EPH.exists():
        print("::warning::Distribución: no está la base de la EPH (la arma src/indec/pobreza.py).")
        return
    e = pd.read_parquet(EPH)
    e["miembros"] = e.groupby(["CODUSU", "NRO_HOGAR", "ANO4", "TRIMESTRE"])["COMPONENTE"].transform("count")
    e["ipcf"] = e["ITF"] / e["miembros"]
    filas = []
    for (a, t), g in e[e["PONDIH"] > 0].groupby(["ANO4", "TRIMESTRE"]):
        x, w = g["ipcf"].to_numpy(float), g["PONDIH"].to_numpy(float)
        o = np.argsort(x)
        xs, ws = x[o], w[o]
        decil = np.minimum((np.cumsum(ws) / ws.sum() * 10).astype(int), 9)
        part = pd.Series(xs * ws).groupby(decil).sum() / (xs * ws).sum() * 100
        prom_dec = pd.Series(xs * ws).groupby(decil).sum() / pd.Series(ws).groupby(decil).sum()
        mediana = xs[np.searchsorted(np.cumsum(ws), ws.sum() / 2)]
        fila = {"fecha": pd.Timestamp(f"{int(a)}-{3 * int(t) - 2:02d}-01"), "gini": gini(x, w),
                "promedio": np.average(x, weights=w), "mediana": mediana, "brecha": prom_dec.iloc[-1] / prom_dec.iloc[0]}
        fila.update({f"decil_{d + 1}": part.get(d, np.nan) for d in range(10)})
        filas.append(fila)
    r = pd.DataFrame(filas).set_index("fecha")

    for (a, t), oficial in CONTROL.items():
        f = pd.Timestamp(f"{a}-{3 * t - 2:02d}-01")
        if f in r.index and abs(r.loc[f, "gini"] - oficial) > 0.003:
            print(f"::warning::Distribución: el Gini de {a}T{t} da {r.loc[f, 'gini']:.3f} y el oficial es {oficial}; "
                  "no se guarda nada.")
            return

    # ingreso per cápita real: deflactado por el IPC promedio del trimestre, en pesos del último trimestre
    try:
        from derivadas.calcular import serie
        ipc = serie("indec_ipc_nivel_general")
        ipc_t = ipc.resample("QS").mean().reindex(r.index)
        r["promedio_real"] = r["promedio"] / ipc_t * ipc_t.dropna().iloc[-1]
        ultimo_ipc = ipc_t.dropna().index[-1]
    except Exception:  # noqa: BLE001
        ultimo_ipc = None

    base = ("Ingreso per cápita familiar de las personas (EPH, 31 aglomerados, ponderador PONDIH). "
            "Replica las cifras oficiales del INDEC.")
    defin = {
        "gini": ("Coeficiente de Gini del ingreso per cápita familiar", "Índice (0 a 1)", "0 = igualdad total, 1 = desigualdad total."),
        "promedio": ("Ingreso per cápita familiar promedio", "$ corrientes", ""),
        "mediana": ("Ingreso per cápita familiar mediano", "$ corrientes", "La mitad de las personas vive en hogares con menos."),
        "brecha": ("Brecha de ingresos: decil 10 sobre decil 1 (promedios)", "Veces", "Ingreso per cápita promedio del 10% más rico dividido el del 10% más pobre."),
        "promedio_real": (f"Ingreso per cápita familiar promedio, real (pesos de {ultimo_ipc:%m/%Y})" if ultimo_ipc else "",
                          "$ constantes", "Deflactado por el IPC nivel general promedio del trimestre."),
    }
    defin.update({f"decil_{d}": (f"Participación del decil {d} en el ingreso total", "% del ingreso",
                                 f"Porcentaje del ingreso per cápita familiar total que recibe el decil {d} "
                                 "(1 = 10% más pobre, 10 = 10% más rico).") for d in range(1, 11)})
    metas, obs = [], []
    for col, (nombre, unidad, desc) in defin.items():
        if col not in r or not nombre:
            continue
        s = r[col].dropna()
        sid = f"club_distribucion_{col}"
        metas.append({"id": sid, "nombre": nombre, "fuente": FUENTE, "categoria": "Distribución del ingreso",
                      "unidad": unidad, "frecuencia": "T", "id_api_bcra": None,
                      "archivo_origen": "src/indec/distribucion.py", "descripcion": f"{desc} {base}".strip()})
        obs.append(pd.DataFrame({"serie_id": sid, "fecha": s.index.strftime("%Y-%m-%d"), "valor": s.round(4).values}))
    SALIDA.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(metas).astype({"id_api_bcra": "Int64"}).to_csv(SALIDA / "series.csv", index=False)
    pd.concat(obs).to_csv(SALIDA / "observaciones.csv", index=False)
    print(f"Distribución: {len(metas)} series, {r.index.min():%Y}T1 a {r.index.max():%Y-%m}; "
          f"Gini último {r['gini'].iloc[-1]:.3f}")


if __name__ == "__main__":
    main()
