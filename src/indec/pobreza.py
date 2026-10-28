"""Pobreza e indigencia (metodología INDEC) y efecto de los precios relativos de la canasta.

1. Descarga la EPH individual (2017 en adelante), las canastas CBA/CBT por región y la tabla
   de adulto equivalente desde el espejo de pyeph (github.com/reflejar/pyeph-data). Los
   trimestres de la EPH que el espejo todavía no tiene se bajan directo de INDEC, y la canasta
   de GBA se completa con la serie mensual de INDEC (las regiones solo salen semestralmente).
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
INDEC_EPH = "https://www.indec.gob.ar/ftp/cuadros/menusuperior/eph/EPH_usu_{t}_Trim_{a}_txt.zip"
INDEC_CANASTAS = "https://www.indec.gob.ar/ftp/cuadros/sociedad/serie_cba_cbt.xls"
NAVEGADOR = {"User-Agent": "Mozilla/5.0 (club-economia-uade; datos abiertos)"}
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
def eph_indec(anio, trim):
    """Base individual de un trimestre bajada de INDEC (para los que el espejo todavía no tiene)."""
    try:
        r = requests.get(INDEC_EPH.format(t=trim, a=anio), headers=NAVEGADOR, timeout=300)
    except requests.RequestException:
        return None
    if not (r.ok and r.content[:2] == b"PK"):
        return None
    return leer_txt_indec(r.content)


def leer_txt_indec(contenido):
    z = zipfile.ZipFile(io.BytesIO(contenido))
    nombres = [n for n in z.namelist() if n.lower().endswith(".txt") and "individual" in n.lower()]
    if not nombres:
        return None
    return pd.read_csv(z.open(nombres[0]), sep=";", usecols=lambda x: x in COLUMNAS, low_memory=False)


def normalizar(df):
    for col in ["ITF", "PONDIH", "PONDERA", "CH04", "CH06", "REGION", "DECIFR", "ANO4", "TRIMESTRE"]:
        if not pd.api.types.is_numeric_dtype(df[col]):
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ".").str.strip(), errors="coerce")
    return df[COLUMNAS]


def eph():
    partes, anio, trim, faltas = [], 2017, 1, 0
    while faltas < 2:  # corta cuando no encuentra dos trimestres seguidos
        c = bajar(f"individual/base_individual_{anio}T{trim}.zip")
        df = csv_de_zip(c, usecols=lambda x: x in COLUMNAS, low_memory=False) if c else eph_indec(anio, trim)
        if df is None:
            faltas += 1
        else:
            faltas = 0
            if not c:
                print(f"EPH {anio}T{trim}: bajada de INDEC (no está en el espejo)")
            partes.append(normalizar(df))
        anio, trim = (anio + 1, 1) if trim == 4 else (anio, trim + 1)
    base = pd.concat(partes, ignore_index=True)
    print(f"EPH: {len(partes)} trimestres, hasta {base.ANO4.max()}T{base[base.ANO4 == base.ANO4.max()].TRIMESTRE.max()}")
    return base


def canastas():
    """Canastas por región (espejo de pyeph) con GBA extendida hasta el último mes que publicó INDEC."""
    hoy = pd.Timestamp.today()
    for meses_atras in range(0, 36):  # busca la versión más reciente publicada en el espejo
        f = (hoy - pd.DateOffset(months=meses_atras)).strftime("%Y-%m")
        cba, cbt = bajar(f"canastas/cba_{f}.zip"), bajar(f"canastas/cbt_{f}.zip")
        if cba and cbt:
            leer = lambda c: csv_de_zip(c, parse_dates=["indice_tiempo"]).set_index("indice_tiempo")  # noqa: E731
            print(f"Canastas por región: versión {f}")
            return extender_gba(leer(cba), leer(cbt))
    raise RuntimeError("No se encontraron las canastas en el espejo de pyeph")


def gba_indec():
    """Serie mensual CBA/CBT de GBA por adulto equivalente: archivo de INDEC + valores cargados a mano en el repo."""
    partes = []
    try:
        r = requests.get(INDEC_CANASTAS, headers=NAVEGADOR, timeout=120)
        if r.ok:
            partes.append(leer_xls_canastas(r.content))
    except Exception as e:  # noqa: BLE001  (formato nuevo, INDEC caído, etc.: seguimos con lo que hay)
        print(f"No se pudo leer serie_cba_cbt.xls de INDEC: {e}")
    manual = RAW / "canastas" / "cba_cbt_gba.csv"
    if manual.exists():
        partes.append(pd.read_csv(manual, parse_dates=["fecha"]).set_index("fecha")[["cba", "cbt"]])
    if not partes:
        return pd.DataFrame(columns=["cba", "cbt"])
    gba = pd.concat(partes)
    return gba[~gba.index.duplicated(keep="first")].sort_index()  # prioridad: el archivo de INDEC


MESES = {m: i for i, m in enumerate(["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                                     "septiembre", "octubre", "noviembre", "diciembre"], 1)}


def leer_xls_canastas(contenido):
    """Busca en serie_cba_cbt.xls las filas  fecha | CBA | inversa de Engel | CBT  del adulto equivalente.

    Acepta la fecha en una celda (2026-08-01) o separada en año y nombre del mes, como en los cuadros de INDEC.
    """
    hoja = pd.read_excel(io.BytesIO(contenido), header=None, sheet_name=0)
    filas, anio = [], None
    for _, fila in hoja.iterrows():
        celdas = list(fila.values)
        fecha, resto = None, celdas[1:]
        if isinstance(celdas[0], (pd.Timestamp, np.datetime64)) or hasattr(celdas[0], "year"):
            fecha = pd.Timestamp(celdas[0])
        else:
            a = pd.to_numeric(celdas[0], errors="coerce")
            anio = int(a) if pd.notna(a) and 2000 < a < 2100 else anio
            mes = MESES.get(str(celdas[1]).strip().lower().rstrip("*")) if len(celdas) > 1 else None
            if anio and mes:
                fecha, resto = pd.Timestamp(anio, mes, 1), celdas[2:]
        nums = pd.to_numeric(pd.Series(resto), errors="coerce").dropna()
        if fecha is not None and len(nums) >= 3:
            filas.append((fecha.to_period("M").to_timestamp(), nums.iloc[0], nums.iloc[2]))
    df = pd.DataFrame(filas, columns=["fecha", "cba", "cbt"]).set_index("fecha")
    if df.empty or not (df["cbt"] > df["cba"]).all():
        raise ValueError("estructura inesperada")
    return df[~df.index.duplicated(keep="last")]


def extender_gba(cba, cbt):
    """Agrega a la columna de GBA los meses que INDEC ya publicó y el espejo todavía no.

    Antes de usar la serie de INDEC la valida contra los meses en común: si no coincide, no la usa.
    Las demás regiones quedan vacías en esos meses (INDEC las publica con el informe semestral).
    """
    gba = gba_indec()
    comun = gba.index.intersection(cba.index)
    if gba.empty or comun.empty:
        return cba, cbt
    desvio = max((gba.loc[comun, "cba"] / cba.loc[comun, "gran_buenos_aires"] - 1).abs().max(),
                 (gba.loc[comun, "cbt"] / cbt.loc[comun, "gran_buenos_aires"] - 1).abs().max())
    if desvio > 0.005:  # 0,5%: las diferencias menores son de redondeo entre las dos publicaciones
        print(f"::warning::La serie de canastas de GBA no coincide con la del espejo (desvío {desvio:.2%}); no se usa")
        return cba, cbt
    nuevos = gba.index.difference(cba.index)
    if nuevos.empty:
        return cba, cbt
    cba = pd.concat([cba, gba.loc[nuevos, ["cba"]].rename(columns={"cba": "gran_buenos_aires"})]).sort_index()
    cbt = pd.concat([cbt, gba.loc[nuevos, ["cbt"]].rename(columns={"cbt": "gran_buenos_aires"})]).sort_index()
    print(f"Canasta GBA extendida con INDEC hasta {nuevos.max():%m/%Y}")
    return cba.rename_axis("indice_tiempo"), cbt.rename_axis("indice_tiempo")


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
        # solo meses con las seis regiones; y solo trimestres con sus tres meses
        c = c[c.index >= BASE].dropna().copy()
        c["ANO4"], c["TRIMESTRE"] = c.index.year, (c.index.month - 1) // 3 + 1
        g = c.groupby(["ANO4", "TRIMESTRE"])
        return (g.mean()[g.size() == 3].stack().rename(nombre)
                .rename_axis(["ANO4", "TRIMESTRE", "region"]))
    lin = pd.concat([trimestral(v, k) for k, v in lineas.items()], axis=1).dropna().reset_index()

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
                                "Es la línea de " + ("indigencia." if nombre == "cba" else "pobreza.") +
                                (" GBA se actualiza todos los meses; el resto de las regiones, con cada informe "
                                 "semestral de pobreza." if col == "gran_buenos_aires" else ""))
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

    oficial = pd.read_csv(RAW / "pobreza_oficial.csv", parse_dates=["semestre"]).set_index("semestre")
    for col, x in [("pobreza", "Pobreza"), ("indigencia", "Indigencia")]:
        agregar(f"indec_{col}_oficial", oficial[col], nombre=f"{x} oficial INDEC (% de personas)", fuente="INDEC",
                categoria="Pobreza", unidad="%", frecuencia="S",
                descripcion=f"{x} publicada por INDEC en el informe semestral (31 aglomerados). Se carga a mano en "
                            "data/raw/indec/pobreza_oficial.csv cuando sale cada informe.")

    comunes = dict(fuente=FUENTE_PROPIA, categoria="Elaboración propia", frecuencia="S")
    met = ("Personas en hogares con ingreso total familiar menor a la {l} de su región multiplicada por los adultos "
           "equivalentes del hogar. EPH, 31 aglomerados urbanos, ponderador PONDIH, canasta promedio del trimestre. "
           "Replica la cifra oficial de INDEC con diferencias de hasta 0,2 puntos en pobreza y 0,4 en indigencia.")
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
