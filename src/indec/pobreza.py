"""Pobreza e indigencia (metodología INDEC) y efecto de los precios relativos de la canasta.

1. Descarga la EPH individual (2017 en adelante), las canastas CBA/CBT por región y la tabla
   de adulto equivalente desde el espejo de pyeph (github.com/reflejar/pyeph-data).
2. Calcula pobreza e indigencia de personas por semestre (31 aglomerados): un hogar es pobre
   si su ingreso total familiar (ITF) es menor que la CBT de su región por la cantidad de
   adultos equivalentes; indigente si es menor que la CBA. Ponderador: PONDIH.
3. Contrafactual: repite el cálculo con canastas que siguen al IPC nivel general desde
   dic-2016. La diferencia es el efecto de que la canasta de los pobres suba más (o menos)
   que la inflación promedio.

Uso: python src/indec/pobreza.py
"""
import io
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
from derivadas.calcular import serie  # noqa: E402  (lee de Supabase o de los CSV locales)

ESPEJO = "https://raw.githubusercontent.com/reflejar/pyeph-data/master"
RAW = RAIZ / "data" / "raw" / "indec"
SALIDA = RAIZ / "data" / "processed" / "pobreza"
BASE = pd.Timestamp("2016-12-01")  # inicio del IPC nacional
REGIONES = {1: "gran_buenos_aires", 40: "noroeste", 41: "noreste", 42: "cuyo", 43: "pampeana", 44: "patagonia"}
NOMBRE_REGION = {"gran_buenos_aires": "GBA", "noroeste": "Noroeste", "noreste": "Noreste", "cuyo": "Cuyo",
                 "pampeana": "Pampeana", "patagonia": "Patagonia"}
COLUMNAS = ["CODUSU", "ANO4", "TRIMESTRE", "NRO_HOGAR", "COMPONENTE", "REGION", "AGLOMERADO",
            "CH03", "CH04", "CH06", "ITF", "DECIFR", "PONDIH", "PONDERA"]
FUENTE_PROPIA = "Club de Economía UADE (elaboración propia)"
ESTRATOS = {  # id: (nombre, descripción)
    "indigente": ("Indigentes", "ingreso familiar menor a la Canasta Básica Alimentaria"),
    "pobre_no_indigente": ("Pobres no indigentes", "ingreso entre la CBA y la CBT"),
    "1_1.1": ("Vulnerables: hasta 10% arriba de la línea", "ingreso entre 1 y 1,1 veces la CBT"),
    "1.1_1.25": ("Vulnerables: 10% a 25% arriba de la línea", "ingreso entre 1,1 y 1,25 veces la CBT"),
    "1.25_1.5": ("Vulnerables: 25% a 50% arriba de la línea", "ingreso entre 1,25 y 1,5 veces la CBT"),
    "1.5_2": ("Entre 1,5 y 2 líneas de pobreza", "ingreso entre 1,5 y 2 veces la CBT"),
    "2_mas": ("Más de 2 líneas de pobreza", "ingreso de 2 veces la CBT o más"),
}


def bajar(ruta):
    r = requests.get(f"{ESPEJO}/{ruta}", timeout=120)
    return r.content if r.ok and r.content[:2] == b"PK" else None


def csv_de_zip(contenido, **kw):
    z = zipfile.ZipFile(io.BytesIO(contenido))
    return pd.read_csv(z.open(z.namelist()[0]), **kw)


# ---------------------------------------------------------------- descarga
def eph():
    partes, anio, trim, faltas = [], 2017, 1, 0
    while faltas < 2:  # corta cuando no encuentra dos trimestres seguidos
        c = bajar(f"individual/base_individual_{anio}T{trim}.zip")
        if c is None:
            faltas += 1
        else:
            faltas = 0
            df = csv_de_zip(c, usecols=lambda x: x in COLUMNAS, low_memory=False)
            for col in ["ITF", "PONDIH", "PONDERA", "CH04", "CH06", "REGION", "DECIFR", "ANO4", "TRIMESTRE"]:
                if df[col].dtype == object:
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ".").str.strip(), errors="coerce")
            partes.append(df[COLUMNAS])
        anio, trim = (anio + 1, 1) if trim == 4 else (anio, trim + 1)
    base = pd.concat(partes, ignore_index=True)
    print(f"EPH: {len(partes)} trimestres, hasta {base.ANO4.max()}T{base[base.ANO4 == base.ANO4.max()].TRIMESTRE.max()}")
    return base


def canastas():
    hoy = pd.Timestamp.today()
    for meses_atras in range(0, 36):  # busca la versión más reciente publicada en el espejo
        f = (hoy - pd.DateOffset(months=meses_atras)).strftime("%Y-%m")
        cba, cbt = bajar(f"canastas/cba_{f}.zip"), bajar(f"canastas/cbt_{f}.zip")
        if cba and cbt:
            leer = lambda c: csv_de_zip(c, parse_dates=["indice_tiempo"]).set_index("indice_tiempo")  # noqa: E731
            print(f"Canastas: versión {f}")
            return leer(cba), leer(cbt)
    raise RuntimeError("No se encontraron las canastas en el espejo de pyeph")


# ---------------------------------------------------------------- cálculo
def tasas(hog, linea):
    pobre = (hog["ITF"] < hog["ae"] * hog[linea]) * hog["personas"]
    return pobre.groupby(hog["semestre"]).sum() / hog["personas"].groupby(hog["semestre"]).sum() * 100


def calcular(base, ae, cba, cbt, ipc):
    factor = (ipc / ipc[BASE]).reindex(cba.index)
    contraf = lambda c: pd.DataFrame(np.outer(factor.values, c.loc[BASE].values),  # noqa: E731
                                     index=c.index, columns=c.columns)
    lineas = {"cba": cba, "cbt": cbt, "cba_cf": contraf(cba), "cbt_cf": contraf(cbt),
              "cbt_rez": cbt.shift(1)}  # canasta del mes anterior, el mismo al que refieren los ingresos

    def trimestral(c, nombre):
        c = c[c.index >= BASE].copy()
        c["ANO4"], c["TRIMESTRE"] = c.index.year, (c.index.month - 1) // 3 + 1
        return (c.groupby(["ANO4", "TRIMESTRE"]).mean().stack().rename(nombre)
                .rename_axis(["ANO4", "TRIMESTRE", "region"]))
    lin = pd.concat([trimestral(v, k) for k, v in lineas.items()], axis=1).reset_index()

    e = base[base["PONDIH"] > 0].merge(ae, on=["CH04", "CH06"])
    e["region"] = e["REGION"].map(REGIONES)
    hog = (e.groupby(["CODUSU", "NRO_HOGAR", "ANO4", "TRIMESTRE"])
           .agg(ITF=("ITF", "first"), region=("region", "first"), ae=("adequi", "sum"), personas=("PONDIH", "sum"))
           .reset_index().merge(lin, on=["ANO4", "TRIMESTRE", "region"]))
    hog["semestre"] = pd.to_datetime(hog["ANO4"].astype(str) + "-" + np.where(hog["TRIMESTRE"] <= 2, "01", "07") + "-01")
    # solo semestres completos (dos trimestres con canasta disponible)
    completos = hog.groupby("semestre")["TRIMESTRE"].nunique() == 2
    hog = hog[hog["semestre"].isin(completos[completos].index)]
    r = pd.DataFrame({k: tasas(hog, k) for k in lineas})
    poblacion = hog.groupby("semestre")["personas"].sum() / 2

    ratio = hog["ITF"] / (hog["ae"] * hog["cbt"])
    estrato = pd.cut(ratio, [-np.inf, 1, 1.1, 1.25, 1.5, 2, np.inf], right=False, labels=list(ESTRATOS)[1:]).astype(str)
    estrato = estrato.where(hog["ITF"] >= hog["ae"] * hog["cba"], "indigente")
    est = hog.assign(estrato=estrato).pivot_table(index="semestre", columns="estrato", values="personas", aggfunc="sum")
    est = est.div(est.sum(axis=1), axis=0)[list(ESTRATOS)] * 100
    return r, poblacion, est


# ---------------------------------------------------------------- salida
def main():
    base, (cba, cbt) = eph(), canastas()
    ae = csv_de_zip(bajar("adulto_equivalente/adulto_equivalente.zip"))
    ipc = serie("indec_ipc_nivel_general")
    r, poblacion, est = calcular(base, ae, cba, cbt, ipc)

    # guardar insumos en el repo (base compacta de la EPH y canastas)
    base.to_parquet(RAW / "eph" / "eph_pobreza_2017_en_adelante.parquet", index=False)
    cba.to_csv(RAW / "canastas" / "cba_regiones.csv")
    cbt.to_csv(RAW / "canastas" / "cbt_regiones.csv")
    ae.to_csv(RAW / "eph" / "adulto_equivalente.csv", index=False)

    metas, obs = [], []

    def agregar(sid, s, **m):
        s = s.dropna()
        metas.append({"id": sid, "id_api_bcra": None, "archivo_origen": "src/indec/pobreza.py", **m})
        obs.append(pd.DataFrame({"serie_id": sid, "fecha": s.index.strftime("%Y-%m-%d"), "valor": s.values}))

    for nombre, c in [("cba", cba), ("cbt", cbt)]:
        for col in c.columns:
            completo = "Canasta Básica Alimentaria" if nombre == "cba" else "Canasta Básica Total"
            agregar(f"indec_{nombre}_{col}", c[col], nombre=f"{completo} por adulto equivalente, {NOMBRE_REGION[col]}",
                    fuente="INDEC", categoria="Canastas básicas", unidad="$", frecuencia="M",
                    descripcion=f"{completo} mensual por adulto equivalente, región {NOMBRE_REGION[col]}. "
                                "Es la línea de " + ("indigencia." if nombre == "cba" else "pobreza."))
    ipc_m = ipc.reindex(cba.index)
    for nombre, c in [("cba", cba), ("cbt", cbt)]:
        real = (c["gran_buenos_aires"] / c.loc[BASE, "gran_buenos_aires"]) / (ipc_m / ipc[BASE]) * 100
        completo = "Canasta Básica Alimentaria" if nombre == "cba" else "Canasta Básica Total"
        agregar(f"club_{nombre}_real", real[real.index >= BASE],
                nombre=f"{completo} (GBA) en términos reales (dic-2016=100)", fuente=FUENTE_PROPIA,
                categoria="Elaboración propia", unidad="Índice", frecuencia="M",
                descripcion=f"{completo} de GBA dividida por el IPC nivel general, base dic-2016=100. Por encima de 100, "
                            "la canasta de los hogares de menores ingresos subió más que la inflación promedio. "
                            "Fuentes: INDEC (canastas e IPC).")

    comunes = dict(fuente=FUENTE_PROPIA, categoria="Elaboración propia", frecuencia="S")
    met = ("Personas en hogares con ingreso total familiar menor a la {l} de su región multiplicada por los adultos "
           "equivalentes del hogar. EPH, 31 aglomerados urbanos, ponderador PONDIH, canasta promedio del trimestre. "
           "Replica la cifra oficial de INDEC con diferencias de hasta 0,2 puntos.")
    agregar("club_pobreza", r["cbt"], nombre="Pobreza (% de personas)", unidad="%", **comunes,
            descripcion=met.format(l="Canasta Básica Total (CBT)"))
    agregar("club_indigencia", r["cba"], nombre="Indigencia (% de personas)", unidad="%", **comunes,
            descripcion=met.format(l="Canasta Básica Alimentaria (CBA)"))
    cf = ("Misma medición pero con una canasta que, desde dic-2016, sube igual que el IPC nivel general. Es la "
          "{x} que habría habido si la canasta de los hogares pobres no hubiera cambiado su precio relativo, "
          "con los mismos ingresos.")
    agregar("club_pobreza_contrafactual", r["cbt_cf"], nombre="Pobreza contrafactual: canasta al ritmo del IPC (%)",
            unidad="%", **comunes, descripcion=cf.format(x="pobreza"))
    agregar("club_indigencia_contrafactual", r["cba_cf"],
            nombre="Indigencia contrafactual: canasta al ritmo del IPC (%)", unidad="%", **comunes,
            descripcion=cf.format(x="indigencia"))
    ef = ("Diferencia entre la {x} medida y la contrafactual, en puntos porcentuales. Positivo: el encarecimiento "
          "relativo de la canasta sumó {x}; negativo: la restó. Acumula los cambios de precios relativos desde dic-2016.")
    agregar("club_efecto_canasta_pobreza", r["cbt"] - r["cbt_cf"], nombre="Efecto de la canasta sobre la pobreza (p.p.)",
            unidad="p.p.", **comunes, descripcion=ef.format(x="pobreza"))
    agregar("club_efecto_canasta_indigencia", r["cba"] - r["cba_cf"],
            nombre="Efecto de la canasta sobre la indigencia (p.p.)", unidad="p.p.", **comunes,
            descripcion=ef.format(x="indigencia"))
    for clave, (nombre, desc) in ESTRATOS.items():
        agregar(f"club_estrato_{clave.replace('.', '')}", est[clave], nombre=f"{nombre} (% de personas)", unidad="%",
                **comunes, descripcion=f"Personas en hogares con {desc} de su región por adulto equivalente. "
                                       "EPH, 31 aglomerados, ponderador PONDIH. Los siete estratos suman 100%.")
    agregar("club_vulnerables", est[["1_1.1", "1.1_1.25", "1.25_1.5"]].sum(axis=1),
            nombre="Vulnerables: hasta 50% por encima de la línea de pobreza (% de personas)", unidad="%", **comunes,
            descripcion="Personas no pobres cuyo ingreso familiar supera la CBT de su hogar en menos de 50%. Con ese "
                        "margen, un golpe habitual (perder un ingreso, un mes de inflación alta) los deja bajo la línea.")
    agregar("club_pobreza_alineada", r["cbt_rez"], nombre="Pobreza con ingresos y canasta del mismo mes (%)",
            unidad="%", **comunes,
            descripcion="Misma medición que la pobreza, pero comparando los ingresos (que la EPH releva para el mes "
                        "anterior a la entrevista) con la canasta de ese mismo mes. Ejercicio de sensibilidad: supone que "
                        "todos los ingresos declarados son del mes anterior; la base pública no trae el mes de entrevista, "
                        "por eso se usan promedios trimestrales.")
    agregar("club_sesgo_inflacion_pobreza", r["cbt"] - r["cbt_rez"],
            nombre="Sobreestimación de la pobreza por desfase ingreso-canasta (p.p.)", unidad="p.p.", **comunes,
            descripcion="Pobreza medida menos pobreza alineada. Crece con la inflación mensual: cuando la canasta sube "
                        "rápido, el ingreso del mes anterior queda corto contra precios nuevos aunque el hogar no haya "
                        "empeorado.")
    infl = (cbt["gran_buenos_aires"].pct_change() * 100)
    infl_sem = infl.groupby([infl.index.year, (infl.index.month > 6)]).mean()
    infl_sem.index = [pd.Timestamp(f"{a}-{'07' if s2 else '01'}-01") for a, s2 in infl_sem.index]
    agregar("club_inflacion_canasta_semestral", infl_sem[infl_sem.index.isin(r.index)],
            nombre="Inflación mensual promedio de la CBT (GBA), por semestre", unidad="%", **comunes,
            descripcion="Variación mensual promedio de la Canasta Básica Total de GBA en cada semestre. Fuente: INDEC.")
    agregar("club_poblacion_eph", poblacion, nombre="Población de los 31 aglomerados (EPH, ponderada)",
            unidad="Personas", **comunes, descripcion="Suma del ponderador PONDIH por semestre. Sirve para pasar puntos "
                                                       "porcentuales a cantidad de personas.")

    SALIDA.mkdir(parents=True, exist_ok=True)
    cols = ["id", "nombre", "fuente", "categoria", "unidad", "frecuencia", "id_api_bcra", "archivo_origen", "descripcion"]
    pd.DataFrame(metas)[cols].astype({"id_api_bcra": "Int64"}).to_csv(SALIDA / "series.csv", index=False)
    pd.concat(obs).to_csv(SALIDA / "observaciones.csv", index=False)
    print(r.round(1).to_string())


if __name__ == "__main__":
    main()
