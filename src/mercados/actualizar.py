"""Dólares (oficial, mayorista, blue, MEP, CCL), brechas y riesgo país desde ArgentinaDatos.

ArgentinaDatos (argentinadatos.com) es una API NO oficial, de código abierto, que recopila
cotizaciones de fuentes públicas. Se usa porque no hay fuente oficial para MEP, CCL ni blue.
Control: su dólar mayorista tiene que coincidir con el tipo de cambio A3500 del BCRA
(bcra_api_84); históricamente la diferencia mediana es 0,08%. Si no coincide, no se guarda nada.

Se publica en datos/ (no se sube a la base).
Uso: python src/mercados/actualizar.py
"""
import os
import sys
from pathlib import Path

import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "data" / "processed" / "mercados"
RAW = RAIZ / "data" / "raw" / "mercados"  # un CSV por cotización, para abrir directo en Excel
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
BLUE_MINIMO = 50  # el blue viene en pesos enteros: desde $50 el redondeo pesa menos de 1%
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
        sys.path.insert(0, str(RAIZ / "src"))
        from almacen import serie
        df = serie("bcra_api_84")
        if df is None:
            return None
    return pd.Series(df["valor"].values, index=pd.to_datetime(df["fecha"])) if len(df) else None


def main():
    series, crudos = {}, {}
    for casa, (sid, nombre) in DOLARES.items():
        datos = traer(f"cotizaciones/dolares/{casa}")
        if datos is None:
            aviso(f"Mercados: no se pudo descargar el dólar {casa}.")
            continue
        df = pd.DataFrame(datos)
        archivo = {"bolsa": "dolar_mep.csv", "contadoconliqui": "dolar_ccl.csv"}.get(casa, f"dolar_{casa}.csv")
        crudos[archivo] = (df[["fecha", "compra", "venta"]], f"{nombre.removesuffix(', venta')}: compra y venta",
                                      "$ por USD")
        series[sid] = pd.Series(pd.to_numeric(df["venta"], errors="coerce").values,
                                index=pd.to_datetime(df["fecha"])).dropna().groupby(level=0).last()
    riesgo = traer("finanzas/indices/riesgo-pais")
    if riesgo:
        df = pd.DataFrame(riesgo)
        crudos["riesgo_pais.csv"] = (df[["fecha", "valor"]], "Riesgo país (EMBI Argentina)", "Puntos básicos")
        series["mercados_riesgo_pais"] = pd.Series(pd.to_numeric(df["valor"], errors="coerce").values,
                                                   index=pd.to_datetime(df["fecha"])).dropna().groupby(level=0).last()
    else:
        aviso("Mercados: no se pudo descargar el riesgo país.")

    # La fuente repite el último dato en fines de semana y feriados: se dejan solo los días con mercado
    # (calendario del A3500 del BCRA; si no está disponible, lunes a viernes).
    bcra = tc_bcra()
    if bcra is not None:
        habiles = bcra.index
        # fuera del rango del calendario del BCRA (antes de 2003 o días nuevos) se usa lunes a viernes
        filtro = lambda idx: idx.isin(habiles) | (idx > habiles.max()) | (idx < habiles.min())  # noqa: E731
    else:
        filtro = lambda idx: idx.dayofweek < 5  # noqa: E731
    for sid in list(series):
        ser = series[sid]
        series[sid] = ser[filtro(ser.index) & (ser.index.dayofweek < 5)]
    for archivo, (df, nombre, unidad) in list(crudos.items()):
        f = pd.to_datetime(df["fecha"])
        crudos[archivo] = (df[filtro(pd.DatetimeIndex(f)) & (f.dt.dayofweek < 5).values], nombre, unidad)

    # control contra el BCRA
    may = series.get("mercados_dolar_mayorista")
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
            extra = (" La fuente publica el blue en pesos enteros: cuando valía entre $4 y $20 (2011-2019), un peso de "
                     "redondeo era 5% a 25% del precio, por eso la serie queda igual durante meses y puede quedar por "
                     "debajo del mayorista. Usar con cuidado antes de 2020.") if casa == "blue" else ""
            agregar(sid, series[sid], nombre, "$ por USD",
                    f"{nombre}. Fuente: ArgentinaDatos (API no oficial que recopila cotizaciones públicas). "
                    f"Solo días hábiles (la fuente repite el último dato en fines de semana y feriados).{extra}")
    for sid, nombre in [("mercados_dolar_mep", "MEP"), ("mercados_dolar_ccl", "CCL"), ("mercados_dolar_blue", "blue")]:
        if sid in series:
            brecha = ((series[sid] / may - 1) * 100).dropna()
            if nombre == "blue":  # antes de que el blue supere BLUE_MINIMO, el redondeo a pesos enteros distorsiona
                desde = series[sid][series[sid] >= BLUE_MINIMO].index.min()
                brecha = brecha[brecha.index >= desde]
            nota_blue = (f" Empieza cuando el blue superó ${BLUE_MINIMO}: antes, el redondeo a pesos enteros de la fuente "
                         "pesaba más de 1% y generaba brechas falsas.") if nombre == "blue" else ""
            agregar(f"mercados_brecha_{nombre.lower()}", brecha, f"Brecha cambiaria: dólar {nombre} vs mayorista",
                    "%", f"Dólar {nombre} dividido el mayorista, menos 1, en %. Mismo día. Fuente: ArgentinaDatos.{nota_blue}")
    if "mercados_riesgo_pais" in series:
        agregar("mercados_riesgo_pais", series["mercados_riesgo_pais"], "Riesgo país (EMBI Argentina)",
                "Puntos básicos", "Diferencial de tasa de los bonos argentinos en dólares contra los del Tesoro de "
                                  "EE.UU. (índice EMBI de JP Morgan). Fuente: ArgentinaDatos.")

    SALIDA.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(metas).astype({"id_api_bcra": "Int64"}).to_csv(SALIDA / "series.csv", index=False)
    pd.concat(obs).to_csv(SALIDA / "observaciones.csv", index=False)

    RAW.mkdir(parents=True, exist_ok=True)
    indice = []
    for archivo, (df, nombre, unidad) in crudos.items():
        df = df.sort_values("fecha")
        df.to_csv(RAW / archivo, index=False)
        indice.append({"archivo": archivo, "serie": nombre, "unidad": unidad, "frecuencia": "Diaria (días hábiles)",
                       "desde": df["fecha"].min(), "hasta": df["fecha"].max(), "fuente": FUENTE,
                       "advertencia": "Valores en pesos enteros: antes de 2020 el redondeo pesa 5-25% del precio."
                       if archivo == "dolar_blue.csv" else ""})
    brechas = pd.DataFrame({f"brecha_{n}": s for n, s in [
        (sid.removeprefix("mercados_brecha_"), ser) for sid, ser in
        [(m["id"], o.set_index("fecha")["valor"]) for m, o in zip(metas, obs)] if sid.startswith("mercados_brecha_")]})
    if not brechas.empty:
        brechas.index.name = "fecha"
        brechas.sort_index().round(2).to_csv(RAW / "brechas.csv")
        indice.append({"archivo": "brechas.csv", "serie": "Brechas MEP, CCL y blue contra el mayorista",
                       "unidad": "%", "frecuencia": "Diaria", "desde": brechas.index.min(),
                       "hasta": brechas.index.max(), "fuente": "Cálculo propio con datos de ArgentinaDatos",
                       "advertencia": f"La brecha blue empieza cuando el blue superó ${BLUE_MINIMO} (redondeo de la fuente)."})
    pd.DataFrame(indice).to_csv(RAW / "INDICE.csv", index=False)


if __name__ == "__main__":
    main()
