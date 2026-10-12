"""Limpia los archivos crudos del BCRA y los lleva al formato de la base.

Genera:
    data/processed/bcra/series.csv         (metadatos: una fila por serie)
    data/processed/bcra/observaciones.csv  (serie_id, fecha, valor)

Uso:
    python src/bcra/limpiar.py
"""
import re
from pathlib import Path

import pandas as pd
from openpyxl.utils import column_index_from_string

RAIZ = Path(__file__).resolve().parents[2]
RAW = RAIZ / "data" / "raw" / "bcra"
SALIDA = RAIZ / "data" / "processed" / "bcra"

HOJAS = {  # nombre en la hoja API_Series -> nombre real de la hoja
    "BASE MONETARIA": "BASE MONETARIA",
    "RESERVAS": "RESERVAS",
    "DEPOSITOS": "DEPOSITOS",
    "PRESTAMOS": "PRESTAMOS",
    "TASAS DE MERCADO": "TASAS DE MERCADO",
    "INSTRUMENTOS DEL BCRA": "INSTRUMENTOS DEL BCRA",
    "INTRUMENTOS DEL BCRA": "INSTRUMENTOS DEL BCRA",  # typo del propio BCRA
    "INSTRUMENTOS": "INSTRUMENTOS DEL BCRA",
}
CATEGORIAS = {
    "BASE MONETARIA": "Base monetaria", "RESERVAS": "Reservas", "DEPOSITOS": "Depósitos",
    "PRESTAMOS": "Préstamos", "TASAS DE MERCADO": "Tasas de mercado",
    "INSTRUMENTOS DEL BCRA": "Instrumentos del BCRA",
}


def unidad_desde_nombre(nombre):
    n = nombre.lower()
    if "millones de usd" in n:
        return "Millones de USD"
    if "millones de $" in n:
        return "Millones de $"
    if "%" in n:
        return "%"
    if "tipo de cambio" in n:
        return "$ por USD"
    return None


def a_largo(fechas, valores, serie_id):
    df = pd.DataFrame({"fecha": pd.to_datetime(fechas, errors="coerce"),
                       "valor": pd.to_numeric(valores, errors="coerce")})
    df = df.dropna()
    if df["fecha"].duplicated().any():
        raise ValueError(f"{serie_id}: fechas duplicadas, revisar la estructura del archivo")
    df.insert(0, "serie_id", serie_id)
    return df


def bloque_diario(d, fila_inicio=9):
    """Algunas hojas apilan debajo del bloque diario otros bloques mensuales
    (promedio mensual, variaciones). Se toma solo el diario: desde la primera
    fila de datos hasta que la fecha vuelve hacia atrás."""
    datos = d.iloc[fila_inicio:]
    fechas = pd.to_datetime(datos.iloc[:, 0], errors="coerce")
    retrocede = fechas.diff().dt.days <= 0
    if retrocede.any():
        datos = datos.loc[: retrocede.idxmax()].iloc[:-1]
    return datos


def series_xlsm():
    """SerieReservas.xlsm: principales variables. Cada columna mapeada a su IdVariable de la API."""
    archivo = RAW / "reservas" / "SerieReservas.xlsm"
    mapa = pd.read_excel(archivo, sheet_name="API_Series", header=None, skiprows=4).iloc[:, :4]
    mapa.columns = ["id_api", "nombre", "hoja", "columna"]
    mapa = mapa.dropna(subset=["id_api", "hoja", "columna"])

    hojas = {}
    metas, obs = [], []
    for _, m in mapa.iterrows():
        hoja = HOJAS.get(str(m["hoja"]).strip().upper())
        if hoja is None:
            print(f"[aviso] hoja desconocida: {m['hoja']} (id {m['id_api']})")
            continue
        if hoja not in hojas:
            hojas[hoja] = pd.read_excel(archivo, sheet_name=hoja, header=None)
        d = hojas[hoja]
        col = column_index_from_string(str(m["columna"]).strip()) - 1
        datos = bloque_diario(d)
        serie_id = f"bcra_api_{int(m['id_api'])}"
        o = a_largo(datos.iloc[:, 0], datos.iloc[:, col], serie_id)
        if o.empty:
            continue
        nombre = re.sub(r"\s+", " ", str(m["nombre"])).strip()
        metas.append({"id": serie_id, "nombre": nombre, "fuente": "BCRA",
                      "categoria": CATEGORIAS[hoja], "unidad": unidad_desde_nombre(nombre),
                      "frecuencia": "D", "id_api_bcra": int(m["id_api"]),
                      "archivo_origen": "bcra/reservas/SerieReservas.xlsm"})
        obs.append(o)
    return metas, obs


def itcrm():
    """ITCRMSerie.xlsx: índice de tipo de cambio real multilateral y bilaterales (diario)."""
    d = pd.read_excel(RAW / "tipo_de_cambio" / "ITCRMSerie.xlsx",
                      sheet_name="ITCRM y bilaterales", header=None)
    encabezados, datos = d.iloc[1], d.iloc[2:]
    metas, obs = [], []
    for col in range(1, d.shape[1]):
        nombre = str(encabezados[col]).strip()
        if nombre in ("nan", ""):
            continue
        sufijo = re.sub(r"[^a-z0-9]+", "_", nombre.lower()
                        .translate(str.maketrans("áéíóú", "aeiou"))).strip("_")
        serie_id = f"bcra_{sufijo}"
        o = a_largo(datos.iloc[:, 0], datos.iloc[:, col], serie_id)
        if o.empty:
            continue
        metas.append({"id": serie_id, "nombre": f"{nombre} (base 17-12-15=100)", "fuente": "BCRA",
                      "categoria": "Tipo de cambio", "unidad": "Índice", "frecuencia": "D",
                      "id_api_bcra": None, "archivo_origen": "bcra/tipo_de_cambio/ITCRMSerie.xlsx"})
        obs.append(o)
    return metas, obs


def bandas():
    """Bandas cambiarias: límites inferior y superior (incluye fechas futuras ya anunciadas)."""
    d = pd.read_excel(RAW / "tipo_de_cambio" / "serie-completa-bandas-cambiarias.xlsx", header=None)
    datos = d.iloc[7:]
    metas, obs = [], []
    for col, (sid, nombre) in {3: ("bcra_banda_inferior", "Banda cambiaria inferior"),
                               4: ("bcra_banda_superior", "Banda cambiaria superior")}.items():
        obs.append(a_largo(datos.iloc[:, 2], datos.iloc[:, col], sid))
        metas.append({"id": sid, "nombre": nombre, "fuente": "BCRA", "categoria": "Tipo de cambio",
                      "unidad": "$ por USD", "frecuencia": "D", "id_api_bcra": None,
                      "archivo_origen": "bcra/tipo_de_cambio/serie-completa-bandas-cambiarias.xlsx"})
    return metas, obs


def main():
    metas, obs = [], []
    for f in (series_xlsm, itcrm, bandas):
        m, o = f()
        print(f"[ok] {f.__name__}: {len(m)} series")
        metas += m
        obs += o

    series = pd.DataFrame(metas).astype({"id_api_bcra": "Int64"})
    observ = pd.concat(obs, ignore_index=True)
    observ["fecha"] = observ["fecha"].dt.strftime("%Y-%m-%d")

    SALIDA.mkdir(parents=True, exist_ok=True)
    series.to_csv(SALIDA / "series.csv", index=False)
    observ.to_csv(SALIDA / "observaciones.csv", index=False)
    print(f"-> {len(series)} series, {len(observ):,} observaciones en {SALIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
