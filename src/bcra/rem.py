"""Relevamiento de Expectativas de Mercado (REM) del BCRA: qué esperan los analistas.

Fuente: libro histórico oficial del BCRA, hoja "Base de Datos Completa" (una fila por encuesta,
variable y período pronosticado, con mediana, percentiles y cantidad de participantes). Estructura
documentada también en github.com/ncachanosky/argentina-economic-monitor.

Cada serie se fecha por el mes de la encuesta (cierra a fin de mes y se publica a comienzos del
siguiente). Controles: al menos 60 encuestas y valores dentro de rangos posibles; si no, se conservan
los datos anteriores. Guarda en data/processed/rem/ (solo repo). Uso: python src/bcra/rem.py
"""
import io
import re
from pathlib import Path

import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "data" / "processed" / "rem"
RAW = RAIZ / "data" / "raw" / "bcra" / "rem"
URL = ("https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/informes/"
       "relevamiento-expectativas-mercado-historico.xlsx")
VARIABLES = {  # nombre en el libro (minúsculas) -> clave
    "precios minoristas (ipc nivel general; indec)": "ipc",
    "precios minoristas (ipc núcleo; indec)": "nucleo",
    "tipo de cambio nominal": "dolar",
    "pib a precios constantes": "pib",
}
ESTADISTICOS = {"Mediana": "mediana", "Percentil 10": "p10", "Percentil 90": "p90",
                "Cantidad de participantes": "participantes"}
FUENTE = "BCRA (REM)"


def periodo(p):
    if hasattr(p, "year"):
        return "mes", pd.Timestamp(p.year, p.month, 1)
    t = str(p).strip().lower()
    if re.fullmatch(r"\d{4}", t):
        return "anio", pd.Timestamp(int(t), 1, 1)
    if t.startswith("próx. 12"):
        return "12m", None
    return None, None


def leer(contenido):
    import openpyxl
    hoja = openpyxl.load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)["Base de Datos Completa"]
    enc, filas = None, []
    for r in hoja.iter_rows(values_only=True):
        if enc is None:
            if r and r[0] == "Fecha de pronóstico":
                enc = [str(c).strip() if c else "" for c in r]
                cols = {k: enc.index(h) for h, k in ESTADISTICOS.items() if h in enc}
            continue
        if not r or not hasattr(r[0], "year"):
            continue
        var = VARIABLES.get(str(r[1] or "").strip().lower())
        tipo, per = periodo(r[3]) if var else (None, None)
        if tipo is None:
            continue
        fila = {"encuesta": pd.Timestamp(r[0].year, r[0].month, 1), "var": var, "tipo": tipo, "periodo": per}
        fila.update({k: float(r[i]) if isinstance(r[i], (int, float)) else None for k, i in cols.items()})
        filas.append(fila)
    df = pd.DataFrame(filas).drop_duplicates(["encuesta", "var", "tipo", "periodo"], keep="last")
    return df


def armar(df):
    out = {}
    doce = lambda v: df[(df["var"] == v) & (df["tipo"] == "12m")].groupby("encuesta").last()  # noqa: E731
    ipc12 = doce("ipc")
    for est, nom in [("mediana", "mediana"), ("p10", "percentil 10"), ("p90", "percentil 90")]:
        out[f"rem_inflacion_12m_{est}"] = (ipc12[est], f"REM: inflación esperada próximos 12 meses ({nom})", "%",
                                           "Inflación minorista (IPC) esperada para los próximos 12 meses.")
    out["rem_participantes"] = (ipc12["participantes"], "REM: cantidad de participantes (inflación 12 meses)",
                                "Participantes", "Cantidad de analistas que respondieron la pregunta.")
    out["rem_dolar_12m_mediana"] = (doce("dolar")["mediana"], "REM: tipo de cambio esperado dentro de 12 meses (mediana)",
                                    "$ por USD", "Tipo de cambio nominal mayorista esperado.")
    for var, nom in [("ipc", "general"), ("nucleo", "núcleo")]:
        m = df[(df["var"] == var) & (df["tipo"] == "mes") & (df["periodo"] == df["encuesta"])]
        out[f"rem_inflacion_mes_{var}"] = (m.groupby("encuesta")["mediana"].last(),
                                          f"REM: inflación {nom} esperada para el mes de la encuesta (mediana)", "% mensual",
                                          "Pronóstico hecho a fin de mes, antes de que el INDEC publique ese dato. "
                                          "Sirve para medir el error de pronóstico.")
    for var, nom, unidad in [("ipc", "Inflación esperada para el año en curso (diciembre contra diciembre)", "%"),
                             ("pib", "Crecimiento del PIB esperado para el año en curso", "%")]:
        a = df[(df["var"] == var) & (df["tipo"] == "anio") & (df["periodo"].dt.year == df["encuesta"].dt.year)]
        out[f"rem_{'inflacion' if var == 'ipc' else 'pib'}_anio_en_curso"] = (
            a.groupby("encuesta")["mediana"].last(), f"REM: {nom[0].lower() + nom[1:]} (mediana)", unidad,
            "Respuesta de cada encuesta para el año calendario en que se hace.")
    return {k: (s.dropna().sort_index(), *rest) for k, (s, *rest) in out.items()}


def main():
    try:
        r = requests.get(URL, timeout=180, headers={"User-Agent": "Mozilla/5.0 (club-economia-uade)"})
        r.raise_for_status()
        series = armar(leer(r.content))
    except Exception as e:  # noqa: BLE001
        print(f"::warning::REM: no se pudo descargar o leer el libro histórico del BCRA ({e}); "
              "se conservan los datos anteriores.")
        return
    s12 = series["rem_inflacion_12m_mediana"][0]
    if len(s12) < 60 or not s12.between(0, 1000).all() or series["rem_dolar_12m_mediana"][0].le(0).any():
        print("::warning::REM: el libro no pasó los controles (pocas encuestas o valores imposibles); no se guarda.")
        return
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "relevamiento-expectativas-mercado-historico.xlsx").write_bytes(r.content)
    metas, obs = [], []
    for sid, (s, nombre, unidad, desc) in series.items():
        if s.empty:
            continue
        metas.append({"id": sid, "nombre": nombre, "fuente": FUENTE, "categoria": "Expectativas", "unidad": unidad,
                      "frecuencia": "M", "id_api_bcra": None, "archivo_origen": "src/bcra/rem.py",
                      "descripcion": f"{desc} Fecha = mes de la encuesta. Libro histórico del REM del BCRA."})
        obs.append(pd.DataFrame({"serie_id": sid, "fecha": s.index.strftime("%Y-%m-%d"), "valor": s.values}))
    SALIDA.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(metas).astype({"id_api_bcra": "Int64"}).to_csv(SALIDA / "series.csv", index=False)
    pd.concat(obs).to_csv(SALIDA / "observaciones.csv", index=False)
    print(f"REM: {len(metas)} series, {len(s12)} encuestas, última {s12.index.max():%Y-%m} "
          f"(inflación 12 meses esperada: {s12.iloc[-1]:.1f}%)")


if __name__ == "__main__":
    main()
