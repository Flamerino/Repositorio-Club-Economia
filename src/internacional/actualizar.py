"""Contexto internacional: FRED (EE.UU. y commodities), Banco Central de Brasil, FMI (WEO) y
Proyecto Maddison. Cada fuente se valida por separado; si una falla, se conservan sus datos
anteriores y las demás siguen.

Se publica en datos/ (no se sube a la base); el reporte de cada corrida queda en
data/raw/internacional/ESTADO.csv. Uso: python src/internacional/actualizar.py
"""
import hashlib
import io
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parents[2]
import sys  # noqa: E402
sys.path.insert(0, str(RAIZ / "src"))
SALIDA = RAIZ / "data" / "processed" / "internacional"
RAW = RAIZ / "data" / "raw" / "internacional"
sesion = requests.Session()
sesion.headers["User-Agent"] = "Mozilla/5.0 (club-economia-uade)"

# ------------------------------------------------------------------ FRED (CSV público, sin clave)
FRED = {  # id FRED: (id propio, nombre, unidad, categoría, rango plausible)
    "FEDFUNDS": ("fred_tasa_fed", "Tasa de fondos federales (Fed)", "% anual", "Estados Unidos", (0, 25)),
    "GS10": ("fred_bono_10_anios_eeuu", "Rendimiento del bono del Tesoro de EE.UU. a 10 años", "% anual",
             "Estados Unidos", (0, 20)),
    "DTWEXBGS": ("fred_dolar_global", "Índice del dólar estadounidense (amplio, ponderado por comercio)",
                 "Índice (ene-2006=100)", "Estados Unidos", (50, 200)),
    "PSOYBUSDM": ("fred_precio_soja", "Precio internacional de la soja", "USD por tonelada", "Commodities", (100, 1500)),
    "PSMEAUSDM": ("fred_precio_harina_soja", "Precio internacional de la harina de soja", "USD por tonelada",
                  "Commodities", (100, 1500)),
    "PSOILUSDM": ("fred_precio_aceite_soja", "Precio internacional del aceite de soja", "USD por tonelada",
                  "Commodities", (200, 3000)),
    "PMAIZMTUSDM": ("fred_precio_maiz", "Precio internacional del maíz", "USD por tonelada", "Commodities", (50, 600)),
    "PWHEAMTUSDM": ("fred_precio_trigo", "Precio internacional del trigo", "USD por tonelada", "Commodities", (50, 800)),
    "POILBREUSDM": ("fred_precio_petroleo_brent", "Precio del petróleo Brent", "USD por barril", "Commodities", (5, 200)),
}
# ------------------------------------------------------------------ Banco Central de Brasil (SGS)
BCB = {  # código SGS: (id, nombre, unidad, frecuencia, rango plausible del último dato)
    24364: ("bcb_ibc_br_desest", "Brasil: IBC-Br, actividad económica desestacionalizada", "Índice (2002=100)", "M", (50, 300)),
    433: ("bcb_ipca_mensual", "Brasil: inflación IPCA mensual", "% mensual", "M", (-3, 10)),
    4189: ("bcb_selic_mensual", "Brasil: tasa Selic acumulada en el mes, anualizada", "% anual", "M", (0, 50)),
    3698: ("bcb_dolar_promedio_mensual", "Brasil: tipo de cambio (reales por dólar), promedio mensual",
           "Reales por USD", "M", (0.5, 20)),
}
# ------------------------------------------------------------------ FMI (DataMapper, WEO)
FMI_IND = {
    "NGDP_RPCH": ("crecimiento_pib", "Crecimiento del PIB real", "% anual"),
    "PCPIPCH": ("inflacion_promedio", "Inflación (promedio anual)", "% anual"),
    "LUR": ("desempleo", "Desempleo", "% de la fuerza laboral"),
    "GGXWDG_NGDP": ("deuda_bruta_gobierno", "Deuda bruta del gobierno general", "% del PIB"),
    "GGXCNL_NGDP": ("resultado_fiscal", "Resultado fiscal del gobierno general", "% del PIB"),
    "BCA_NGDPD": ("cuenta_corriente", "Cuenta corriente", "% del PIB"),
    "NGDPDPC": ("pib_per_capita_usd", "PIB per cápita", "USD corrientes"),
}
PAISES = {"ARG": "Argentina", "BRA": "Brasil", "CHL": "Chile", "URY": "Uruguay", "PRY": "Paraguay",
          "BOL": "Bolivia", "PER": "Perú", "COL": "Colombia", "MEX": "México"}
# ------------------------------------------------------------------ Proyecto Maddison
MADDISON_URLS = ["https://www.rug.nl/ggdc/historicaldevelopment/maddison/data/mpd2023_web.xlsx",
                 "https://dataverse.nl/api/access/datafile/421302"]
MADDISON_SHA256 = "ecc5916ca12789b983fc4be437f8a354bbf4291323605324ac3e0aea4c57cbb6"  # mpd2023_web.xlsx oficial
MADDISON_PAISES = {"ARG": "Argentina", "AUS": "Australia", "CAN": "Canadá", "ESP": "España", "ITA": "Italia",
                   "USA": "Estados Unidos", "BRA": "Brasil", "CHL": "Chile", "URY": "Uruguay", "KOR": "Corea del Sur"}

ESTADO = []


def aviso(fuente, msg):
    ESTADO.append({"fuente": fuente, "estado": "AVISO", "detalle": msg})
    print(f"::warning::{fuente}: {msg}")


def get(url, intentos=2, timeout=30, **kw):
    for intento in range(intentos):
        try:
            r = sesion.get(url, timeout=timeout, **kw)
            if r.ok:
                return r
        except requests.RequestException:
            pass
        time.sleep(2 * (intento + 1))
    return None


def responde(fuente, url, **kw):
    """Un solo intento corto: si la API no contesta, se saltea la fuente entera en vez de esperar serie por serie."""
    if get(url, intentos=1, timeout=20, **kw) is None:
        aviso(fuente, "la API no respondió a tiempo; se conservan los datos anteriores")
        return False
    return True


def registrar(fuente, n):
    ESTADO.append({"fuente": fuente, "estado": "OK", "detalle": f"{n} series"})


def fred():
    out = {}
    if not responde("FRED", "https://fred.stlouisfed.org/graph/fredgraph.csv", params={"id": "FEDFUNDS"}):
        return out
    for codigo, (sid, nombre, unidad, cat, (lo, hi)) in FRED.items():
        r = get("https://fred.stlouisfed.org/graph/fredgraph.csv", params={"id": codigo})
        if r is None:
            aviso("FRED", f"no se pudo descargar {codigo}")
            continue
        df = pd.read_csv(io.StringIO(r.text), na_values=["."])
        col_fecha = df.columns[0]  # "observation_date" (o "DATE" en versiones anteriores)
        s = pd.Series(pd.to_numeric(df[codigo], errors="coerce").values, index=pd.to_datetime(df[col_fecha])).dropna()
        if len(s) < 50 or not (lo <= s.iloc[-1] <= hi):
            aviso("FRED", f"{codigo}: datos fuera de lo esperable (último {s.iloc[-1] if len(s) else 'sin datos'})")
            continue
        freq = "D" if codigo == "DTWEXBGS" else "M"
        out[sid] = (s, nombre, unidad, freq, cat,
                    f"Serie {codigo} de FRED (Federal Reserve Bank of St. Louis). "
                    + ("Precios de commodities del FMI publicados por FRED." if cat == "Commodities" else ""))
    if out:
        registrar("FRED", len(out))
    return out


def bcb():
    out = {}
    if not responde("Banco Central de Brasil", "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados/ultimos/1",
                    params={"formato": "json"}):
        return out
    for codigo, (sid, nombre, unidad, freq, (lo, hi)) in BCB.items():
        r = get(f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados", params={"formato": "json"})
        try:
            df = pd.DataFrame(r.json())
            s = pd.Series(pd.to_numeric(df["valor"], errors="coerce").values,
                          index=pd.to_datetime(df["data"], format="%d/%m/%Y")).dropna()
        except Exception:  # noqa: BLE001
            aviso("Banco Central de Brasil", f"no se pudo leer la serie SGS {codigo}")
            continue
        if len(s) < 24 or not (lo <= s.iloc[-1] <= hi):
            aviso("Banco Central de Brasil", f"SGS {codigo}: datos fuera de lo esperable")
            continue
        out[sid] = (s, nombre, unidad, freq, "Brasil", f"Serie SGS {codigo} del Banco Central do Brasil.")
    if out:
        registrar("Banco Central de Brasil", len(out))
    return out


def fmi():
    out = {}
    if not responde("FMI", "https://www.imf.org/external/datamapper/api/v1/NGDP_RPCH/ARG"):
        return out
    anio = date.today().year
    for ind, (slug, nombre, unidad) in FMI_IND.items():
        r = get(f"https://www.imf.org/external/datamapper/api/v1/{ind}/{'/'.join(PAISES)}")
        try:
            valores = r.json()["values"][ind]
        except Exception:  # noqa: BLE001
            aviso("FMI", f"no se pudo leer {ind}")
            continue
        for iso, serie in valores.items():
            if iso not in PAISES:
                continue
            s = pd.Series({pd.Timestamp(f"{a}-01-01"): v for a, v in serie.items() if v is not None}).sort_index()
            if s.empty:
                continue
            out[f"fmi_{slug}_{iso.lower()}"] = (
                s, f"{nombre}: {PAISES[iso]}", unidad, "A", "Comparación internacional (FMI)",
                f"Indicador {ind} del World Economic Outlook del FMI (DataMapper). Los valores desde {anio} en "
                "adelante son estimaciones y proyecciones del FMI.")
    # control: crecimiento de Argentina contra el Banco Mundial (años ya cerrados)
    from almacen import serie
    bm = serie("bm_crecimiento_pib_arg")
    if "fmi_crecimiento_pib_arg" in out and bm is not None:
        ref = pd.Series(bm["valor"].values, index=pd.to_datetime(bm["fecha"]))
        f = out["fmi_crecimiento_pib_arg"][0]
        comunes = [x for x in ref.index.intersection(f.index) if x.year < anio - 1]
        dif = (f[comunes] - ref[comunes]).abs().median() if comunes else None
        if dif is None or dif > 1.0:
            aviso("FMI", f"el crecimiento de Argentina no coincide con el Banco Mundial (diferencia mediana {dif}); "
                         "no se guarda el FMI")
            return {}
        print(f"Control FMI: crecimiento ARG vs Banco Mundial, diferencia mediana {dif:.2f} p.p. ({len(comunes)} años)")
    if out:
        registrar("FMI", len(out))
    return out


def maddison():
    archivo = RAIZ / "data" / "raw" / "maddison" / "mpd2023_web.xlsx"
    if not archivo.exists():
        for url in MADDISON_URLS:
            r = get(url)
            if r is not None and hashlib.sha256(r.content).hexdigest() == MADDISON_SHA256:
                archivo.parent.mkdir(parents=True, exist_ok=True)
                archivo.write_bytes(r.content)
                break
        else:
            aviso("Proyecto Maddison", "no se pudo descargar el archivo oficial (o no coincide su huella SHA-256)")
            return {}
    d = pd.read_excel(archivo, sheet_name="Full data")
    p = d.pivot_table(index="year", columns="countrycode", values="gdppc")
    if not (10000 < p.loc[2018, "ARG"] < 30000):
        aviso("Proyecto Maddison", "valores de Argentina fuera de lo esperable")
        return {}
    out = {}
    for iso, nombre in MADDISON_PAISES.items():
        s = p[iso].dropna()
        s.index = pd.to_datetime([f"{a}-01-01" for a in s.index])
        out[f"maddison_pib_pc_{iso.lower()}"] = (
            s, f"PIB per cápita histórico: {nombre}", "USD de 2011 (PPA)", "A", "Historia económica",
            "Maddison Project Database 2023 (Bolt y van Zanden, Universidad de Groningen). PIB per cápita en dólares "
            "internacionales de 2011. Antes de 1950 los datos son esporádicos.")
    registrar("Proyecto Maddison", len(out))
    return out


def main():
    from almacen import metas as metas_publicadas, observaciones
    o, m = observaciones("internacional"), metas_publicadas("internacional").set_index("id")
    previas = {k: (g, m.loc[k]) for k, g in o.groupby("serie_id") if k in m.index}
    todas = {}
    for fuente, prefijo in [(fred, "fred_"), (bcb, "bcb_"), (fmi, "fmi_"), (maddison, "maddison_")]:
        nuevas = fuente()
        if not nuevas:  # se conservan las series anteriores de esa fuente
            nuevas = {k: v for k, v in previas.items() if k.startswith(prefijo)}
        todas.update(nuevas)
    if not todas:
        print("::warning::Internacional: no se obtuvo ninguna serie; no se modifican los archivos.")
        return
    metas, obs = [], []
    for sid, v in todas.items():
        if isinstance(v[1], pd.Series):  # conservada de la corrida anterior
            g, m = v
            metas.append({"id": sid, **{k: m[k] for k in ["nombre", "fuente", "categoria", "unidad", "frecuencia",
                                                            "id_api_bcra", "archivo_origen", "descripcion"]}})
            obs.append(g)
            continue
        s, nombre, unidad, freq, cat, desc = v
        fuente = {"fred": "FRED (Reserva Federal de St. Louis)", "bcb": "Banco Central de Brasil", "fmi": "FMI",
                  "maddison": "Proyecto Maddison"}[sid.split("_")[0]]
        metas.append({"id": sid, "nombre": nombre, "fuente": fuente, "categoria": cat, "unidad": unidad,
                      "frecuencia": freq, "id_api_bcra": None, "archivo_origen": "src/internacional/actualizar.py",
                      "descripcion": desc})
        obs.append(pd.DataFrame({"serie_id": sid, "fecha": s.index.strftime("%Y-%m-%d"), "valor": s.values}))
    SALIDA.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(metas).astype({"id_api_bcra": "Int64"}).to_csv(SALIDA / "series.csv", index=False)
    pd.concat(obs).to_csv(SALIDA / "observaciones.csv", index=False)
    RAW.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(ESTADO).to_csv(RAW / "ESTADO.csv", index=False)
    print(f"Internacional: {len(metas)} series. " + "; ".join(f"{e['fuente']}: {e['estado']}" for e in ESTADO))


if __name__ == "__main__":
    main()
