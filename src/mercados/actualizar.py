"""Dólares (oficial, mayorista, blue, MEP, CCL), brechas y riesgo país desde ArgentinaDatos.

ArgentinaDatos (argentinadatos.com) es una API NO oficial, de código abierto, que recopila
cotizaciones de fuentes públicas. Se usa porque no hay fuente oficial para MEP, CCL ni blue.
Control: su dólar mayorista tiene que coincidir con el tipo de cambio A3500 del BCRA
(bcra_api_84); históricamente la diferencia mediana es 0,08%. Si no coincide, no se guarda nada.

Guarda en data/processed/mercados/ (solo repo, no se sube a la base).
Uso: python src/mercados/actualizar.py
"""
import os
import sys
from pathlib import Path

import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "data" / "processed" / "mercados"
FUENTES = [  # la API y, de respaldo, los mismos datos publicados en GitHub
    "https://api.argentinadatos.com/v1/{ruta}",
    "https://raw.githubusercontent.com/enzonotario/argentinadatos.com/main/datos/v1/{ruta}/index.json",
]
DOLARES = {  # casa en la API: (id, nombre)
    "oficial": ("mercados_dolar_oficial", "Dólar oficial minorista (Banco Nación), venta"),
    "mayorista": ("mercados_dolar_mayorista", "Dólar mayorista, venta"),
    "blue": ("mercados_dolar_blue", "Dólar blue (informal), venta"),
    "bolsa": ("mercados_dolar_mep", "Dólar MEP (bolsa), venta"),
    "contadoconliqui": ("mercados_dolar_ccl", "Dólar contado con liquidación, venta"),
}
TOLERANCIA = 0.01  # 1% de diferencia mediana con el BCRA en los últimos dos años
FUENTE = "ArgentinaDatos (no oficial)"


def aviso(msg):
    print(f"::warning::{msg}")


def traer(ruta):
    for url in FUENTES:
        try:
            r = requests.get(url.format(ruta=ruta), timeout=60)
            if r.ok and isinstance(r.json(), list) and r.json():
                return r.json()
        except (requests.RequestException, ValueError):
            continue
    return None


def tc_bcra():
    """Tipo de cambio A3500 del BCRA: de Supabase si hay credenciales, si no del CSV local."""
    if os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY"):
        sys.path.insert(0, str(RAIZ / "src"))
        from supabase_db import leer_serie
        df = pd.DataFrame(leer_serie("bcra_api_84"))
    else:
        archivo = RAIZ / "data" / "processed" / "bcra" / "observaciones.csv"
        if not archivo.exists():
            return None
        o = pd.read_csv(archivo)
        df = o[o["serie_id"] == "bcra_api_84"]
    return pd.Series(df["valor"].values, index=pd.to_datetime(df["fecha"])) if len(df) else None


def main():
    series = {}
    for casa, (sid, nombre) in DOLARES.items():
        datos = traer(f"cotizaciones/dolares/{casa}")
        if datos is None:
            aviso(f"Mercados: no se pudo descargar el dólar {casa}.")
            continue
        df = pd.DataFrame(datos)
        series[sid] = pd.Series(pd.to_numeric(df["venta"], errors="coerce").values,
                                index=pd.to_datetime(df["fecha"])).dropna().groupby(level=0).last()
    riesgo = traer("finanzas/indices/riesgo-pais")
    if riesgo:
        df = pd.DataFrame(riesgo)
        series["mercados_riesgo_pais"] = pd.Series(pd.to_numeric(df["valor"], errors="coerce").values,
                                                   index=pd.to_datetime(df["fecha"])).dropna().groupby(level=0).last()
    else:
        aviso("Mercados: no se pudo descargar el riesgo país.")

    # control contra el BCRA
    may, bcra = series.get("mercados_dolar_mayorista"), tc_bcra()
    if may is None:
        aviso("Mercados: sin dólar mayorista no se puede validar la fuente. No se guarda nada.")
        return
    if bcra is not None:
        comunes = may.index.intersection(bcra.index)
        comunes = comunes[comunes >= comunes.max() - pd.DateOffset(years=2)]
        dif = (may[comunes] / bcra[comunes] - 1).abs().median()
        if len(comunes) < 100 or dif > TOLERANCIA:
            aviso(f"Mercados: el mayorista de ArgentinaDatos difiere {dif:.2%} del BCRA ({len(comunes)} días). "
                  "No se guarda nada.")
            return
        print(f"Control: mayorista vs BCRA, diferencia mediana {dif:.2%} en {len(comunes)} días")
    else:
        print("Control: sin datos del BCRA disponibles, se omite la validación")

    metas, obs = [], []

    def agregar(sid, s, nombre, unidad, desc):
        metas.append({"id": sid, "nombre": nombre, "fuente": FUENTE, "categoria": "Mercados", "unidad": unidad,
                      "frecuencia": "D", "id_api_bcra": None, "archivo_origen": "src/mercados/actualizar.py",
                      "descripcion": desc})
        obs.append(pd.DataFrame({"serie_id": sid, "fecha": s.index.strftime("%Y-%m-%d"), "valor": s.values}))
        print(f"[ok] {sid}: {len(s):,} datos, {s.index.min():%Y-%m-%d} a {s.index.max():%Y-%m-%d}, último {s.iloc[-1]:,.2f}")

    for casa, (sid, nombre) in DOLARES.items():
        if sid in series:
            agregar(sid, series[sid], nombre, "$ por USD",
                    f"{nombre}. Fuente: ArgentinaDatos (API no oficial que recopila cotizaciones públicas).")
    for sid, nombre in [("mercados_dolar_mep", "MEP"), ("mercados_dolar_ccl", "CCL"), ("mercados_dolar_blue", "blue")]:
        if sid in series:
            brecha = ((series[sid] / may - 1) * 100).dropna()
            agregar(f"mercados_brecha_{nombre.lower()}", brecha, f"Brecha cambiaria: dólar {nombre} vs mayorista",
                    "%", f"Dólar {nombre} dividido el mayorista, menos 1, en %. Mismo día. Fuente: ArgentinaDatos.")
    if "mercados_riesgo_pais" in series:
        agregar("mercados_riesgo_pais", series["mercados_riesgo_pais"], "Riesgo país (EMBI Argentina)",
                "Puntos básicos", "Diferencial de tasa de los bonos argentinos en dólares contra los del Tesoro de "
                                  "EE.UU. (índice EMBI de JP Morgan). Fuente: ArgentinaDatos.")

    SALIDA.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(metas).astype({"id_api_bcra": "Int64"}).to_csv(SALIDA / "series.csv", index=False)
    pd.concat(obs).to_csv(SALIDA / "observaciones.csv", index=False)


if __name__ == "__main__":
    main()
