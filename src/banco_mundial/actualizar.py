"""Indicadores anuales del Banco Mundial para comparar Argentina con la región.

API pública del Banco Mundial (api.worldbank.org, sin clave). Control: el crecimiento del PIB
de Argentina tiene que coincidir con el archivo del Banco Mundial guardado en
data/raw/banco_mundial/ (años en común, sin los dos últimos, que se revisan). Si no coincide,
no se guarda nada.

Guarda en data/processed/banco_mundial/ (solo repo, no se sube a la base).
Uso: python src/banco_mundial/actualizar.py
"""
import re
import time
from pathlib import Path

import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "data" / "processed" / "banco_mundial"
REFERENCIA = next((RAIZ / "data" / "raw" / "banco_mundial").glob("API_NY.GDP.MKTP.KD.ZG*.xls"), None)
API = "https://api.worldbank.org/v2/country/{paises}/indicator/{indicador}"

PAISES = {"ARG": "Argentina", "BRA": "Brasil", "CHL": "Chile", "URY": "Uruguay", "PRY": "Paraguay",
          "BOL": "Bolivia", "PER": "Perú", "COL": "Colombia", "MEX": "México",
          "LCN": "América Latina y el Caribe", "WLD": "Mundo"}
INDICADORES = {  # código: (slug, nombre, unidad)
    "NY.GDP.MKTP.KD.ZG": ("crecimiento_pib", "Crecimiento del PIB", "% anual"),
    "FP.CPI.TOTL.ZG": ("inflacion", "Inflación (precios al consumidor)", "% anual"),
    "NY.GDP.PCAP.PP.KD": ("pib_pc_ppa", "PIB per cápita (PPA, dólares internacionales constantes)", "USD PPA constantes"),
    "SL.UEM.TOTL.ZS": ("desempleo", "Desempleo (estimación modelada OIT)", "% de la fuerza laboral"),
    "SI.POV.GINI": ("gini", "Índice de Gini", "Índice (0-100)"),
    "NE.GDI.TOTL.ZS": ("inversion", "Formación bruta de capital (inversión)", "% del PIB"),
    "NE.EXP.GNFS.ZS": ("exportaciones", "Exportaciones de bienes y servicios", "% del PIB"),
    "GC.DOD.TOTL.GD.ZS": ("deuda_gobierno", "Deuda del gobierno central", "% del PIB"),
}
TOLERANCIA = 0.3  # puntos porcentuales de diferencia mediana admitida en el control


def aviso(msg):
    print(f"::warning::{msg}")


def traer(indicador, intentos=3):
    url = API.format(paises=";".join(PAISES), indicador=indicador)
    for intento in range(intentos):
        try:
            r = requests.get(url, params={"format": "json", "per_page": 20000}, timeout=45)
            js = r.json() if r.ok else None
            if isinstance(js, list) and len(js) == 2 and isinstance(js[1], list):
                return js[1]
        except (requests.RequestException, ValueError):
            pass
        time.sleep(2 ** intento)
    return None


def referencia_arg():
    if REFERENCIA is None:
        return None
    d = pd.read_excel(REFERENCIA, sheet_name=0, header=3)
    fila = d[d["Country Code"] == "ARG"].iloc[0]
    anios = [c for c in d.columns if re.fullmatch(r"\d{4}", str(c))]
    return pd.Series({int(a): fila[a] for a in anios}).dropna()


def main():
    filas = []
    primero = traer(next(iter(INDICADORES)), intentos=2)  # chequeo rápido de que la API responde
    if primero is None:
        aviso("Banco Mundial: la API no responde; se mantienen los datos anteriores.")
        return
    for codigo in INDICADORES:
        datos = primero if codigo == next(iter(INDICADORES)) else traer(codigo)
        if datos is None:
            aviso(f"Banco Mundial: no se pudo descargar {codigo}.")
            continue
        for d in datos:
            if d.get("value") is not None:
                filas.append({"indicador": codigo, "pais": d.get("countryiso3code") or d["country"]["id"],
                              "anio": int(d["date"]), "valor": float(d["value"])})
    if not filas:
        aviso("Banco Mundial: no se obtuvo ningún dato; no se modifican los archivos.")
        return
    df = pd.DataFrame(filas)

    ref = referencia_arg()
    nuevo = df[(df.indicador == "NY.GDP.MKTP.KD.ZG") & (df.pais == "ARG")].set_index("anio")["valor"]
    if ref is not None and len(nuevo):
        comunes = [a for a in ref.index.intersection(nuevo.index) if a <= max(ref.index) - 2]
        dif = (nuevo[comunes] - ref[comunes]).abs().median() if comunes else None
        if dif is None or len(comunes) < 20 or dif > TOLERANCIA:
            aviso(f"Banco Mundial: el crecimiento de Argentina no coincide con el archivo de referencia "
                  f"({len(comunes)} años, diferencia mediana {dif}). No se guarda nada.")
            return
        print(f"Control: crecimiento ARG vs archivo de referencia, diferencia mediana {dif:.3f} p.p. en {len(comunes)} años")

    metas, obs = [], []
    for (codigo, pais), g in df.groupby(["indicador", "pais"]):
        if pais not in PAISES:
            continue
        slug, nombre, unidad = INDICADORES[codigo]
        sid = f"bm_{slug}_{pais.lower()}"
        g = g.sort_values("anio")
        metas.append({"id": sid, "nombre": f"{nombre}: {PAISES[pais]}", "fuente": "Banco Mundial",
                      "categoria": "Comparación internacional", "unidad": unidad, "frecuencia": "A",
                      "id_api_bcra": None, "archivo_origen": "src/banco_mundial/actualizar.py",
                      "descripcion": f"Indicador {codigo} del Banco Mundial (World Development Indicators), {PAISES[pais]}."})
        obs.append(pd.DataFrame({"serie_id": sid, "fecha": [f"{a}-01-01" for a in g["anio"]], "valor": g["valor"].values}))
    SALIDA.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(metas).astype({"id_api_bcra": "Int64"}).to_csv(SALIDA / "series.csv", index=False)
    pd.concat(obs).to_csv(SALIDA / "observaciones.csv", index=False)
    print(f"-> {len(metas)} series ({len(INDICADORES)} indicadores × {len(PAISES)} países)")


if __name__ == "__main__":
    main()
