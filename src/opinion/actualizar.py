"""Índice de Confianza en el Gobierno (ICG), Universidad Torcuato Di Tella.

Microdatos: respaldo que mantiene el paquete opinAr (PoliticaArgentina/data_warehouse), que los
baja del sitio de la UTDT con su propio workflow. El índice se calcula igual que opinAr::compute_icg:
promedio de la variable `icg` (0 a 5) ponderado por `ponderacion_utdt`, por ola mensual. Se publican
el índice general, sus cinco componentes y el índice por zona, sexo, edad y educación.

Controles: valores entre 0 y 5; la historia ya guardada no puede cambiar más de 0,05 puntos.
Se publica en datos/ (no se sube a la base). Uso: python src/opinion/actualizar.py
"""
import io
from pathlib import Path

import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "data" / "processed" / "opinion"
URL = "https://raw.githubusercontent.com/PoliticaArgentina/data_warehouse/master/opinAr/data_raw/icg.dta"
FUENTE = "Universidad Torcuato Di Tella (ICG), vía opinAr"
COMPONENTES = {
    "icg": ("Índice de Confianza en el Gobierno (ICG)", "Promedio de los cinco componentes, escala 0 a 5."),
    "eval_gob_rec": ("ICG: evaluación general del gobierno", "Componente del ICG, escala 0 a 5."),
    "benef_gob_rec": ("ICG: gobierno al servicio del interés general", "Componente del ICG, escala 0 a 5."),
    "adm_gp_rec": ("ICG: eficiencia en la administración del gasto público", "Componente del ICG, escala 0 a 5."),
    "cor_gob_rec": ("ICG: honestidad de los funcionarios", "Componente del ICG, escala 0 a 5."),
    "resol_prob_rec": ("ICG: capacidad para resolver los problemas del país", "Componente del ICG, escala 0 a 5."),
}
SEGMENTOS = {"zona": "zona", "sexo": "sexo", "edad": "edad", "edu": "nivel educativo"}
NOMBRES = {"BsAs": "Gran Buenos Aires", "18a29": "18 a 29 años", "30a49": "30 a 49 años", "más50": "50 años o más",
           "TercOUniv": "Terciario o universitario"}  # etiquetas de la UTDT -> nombre para mostrar
TOLERANCIA = 0.05


def aviso(msg):
    print(f"::warning::{msg}")


def slug(txt):
    import re
    import unicodedata
    s = "".join(c for c in unicodedata.normalize("NFD", str(txt).lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def main():
    try:
        r = requests.get(URL, timeout=180)
        r.raise_for_status()
        lector = pd.io.stata.StataReader(io.BytesIO(r.content))
        etiquetas = lector.value_labels()
        d = pd.read_stata(io.BytesIO(r.content), convert_categoricals=False)
    except Exception as e:  # noqa: BLE001
        aviso(f"ICG: no se pudieron descargar los microdatos ({e}). Se mantienen los datos anteriores.")
        return
    w = d["ponderacion_utdt"]
    prom = lambda df: (df[list(COMPONENTES)].mul(w[df.index], axis=0).groupby(df["ola"]).sum()  # noqa: E731
                       .div(w[df.index].groupby(df["ola"]).sum(), axis=0))
    general = prom(d)
    if not general["icg"].between(0, 5).all():
        aviso("ICG: valores fuera de la escala 0-5; no se guarda nada.")
        return

    series = {}
    for col, (nombre, desc) in COMPONENTES.items():
        sid = "utdt_icg" if col == "icg" else f"utdt_icg_{col.removesuffix('_gob_rec').removesuffix('_rec')}"
        series[sid] = (general[col], nombre, desc, "ICG")
    for seg, nombre_seg in SEGMENTOS.items():
        mapa = {int(k): v for k, v in etiquetas.get(seg, {}).items()}
        for codigo, g in d.groupby(seg):
            etiqueta = mapa.get(int(codigo), str(codigo))
            s = prom(g)["icg"]
            mostrar = NOMBRES.get(etiqueta, etiqueta)
            series[f"utdt_icg_{seg}_{slug(etiqueta)}"] = (
                s, f"ICG por {nombre_seg}: {mostrar}", f"ICG de los encuestados con {nombre_seg}: {mostrar}.",
                "ICG por segmento")

    import sys
    sys.path.insert(0, str(RAIZ / "src"))
    from almacen import serie
    previo = serie("utdt_icg")
    if previo is not None:
        viejo = pd.Series(previo["valor"].values, index=pd.to_datetime(previo["fecha"]))
        nuevo = series["utdt_icg"][0]
        comunes = viejo.index.intersection(nuevo.index)
        if len(comunes) and (nuevo[comunes] - viejo[comunes]).abs().max() > TOLERANCIA:
            aviso("ICG: la historia cambió más de lo esperado respecto de lo guardado; no se pisa.")
            return

    metas, obs = [], []
    for sid, (s, nombre, desc, categoria) in series.items():
        s = s.dropna().round(3)
        metas.append({"id": sid, "nombre": nombre, "fuente": FUENTE, "categoria": f"Opinión pública: {categoria}",
                      "unidad": "Índice (0 a 5)", "frecuencia": "M", "id_api_bcra": None,
                      "archivo_origen": "src/opinion/actualizar.py",
                      "descripcion": f"{desc} Encuesta mensual de la Escuela de Gobierno de la UTDT (utdt.edu/icg). "
                                     "Cálculo idéntico a opinAr::compute_icg: promedio ponderado por ponderacion_utdt."})
        obs.append(pd.DataFrame({"serie_id": sid, "fecha": s.index.strftime("%Y-%m-%d"), "valor": s.values}))
    SALIDA.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(metas).astype({"id_api_bcra": "Int64"}).to_csv(SALIDA / "series.csv", index=False)
    pd.concat(obs).to_csv(SALIDA / "observaciones.csv", index=False)
    g = series["utdt_icg"][0]
    print(f"ICG: {len(metas)} series, {len(g)} olas ({g.index.min():%Y-%m} a {g.index.max():%Y-%m}), "
          f"último {g.iloc[-1]:.2f}")


if __name__ == "__main__":
    main()
