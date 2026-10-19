"""Balance cambiario y mercado de cambios del BCRA (anexo estadístico, mensual, millones de USD).

Lee todas las columnas con código (bal001, cap002, mlc010, viajes003...) de las hojas del anexo y arma
el nombre de cada serie con sus encabezados ("Cuenta corriente cambiaria › Bienes › Cobros de
exportaciones de bienes"). Solo filas mensuales (debajo hay totales anuales que se descartan).

Cada semana intenta bajar la versión nueva del sitio del BCRA; la usa solo si coincide con la historia
del archivo anterior (meses de más de 6 meses de antigüedad, diferencia mediana < 1%). Si no puede,
procesa el archivo que ya está en el repo.

Guarda en data/processed/balance_cambiario/ (solo repo). Uso: python src/bcra/balance_cambiario.py
"""
import datetime as dt
import io
import re
from pathlib import Path

import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parents[2]
ARCHIVO = RAIZ / "data" / "raw" / "bcra" / "mercado_de_cambios" / "anexo-estadistico-mercado-cambios-balance-cambiario.xlsx"
SALIDA = RAIZ / "data" / "processed" / "balance_cambiario"
URLS = [f"https://www.bcra.gob.ar/{p}/PublicacionesEstadisticas/{ARCHIVO.name}" for p in ("archivos/Pdfs", "Pdfs")]
HOJAS = {  # hoja: (prefijo de id, categoría)
    "Balance Cambiario": ("bc", "Balance cambiario"),
    "Cta. Financiera por sector": ("bc", "Balance cambiario: cuenta financiera por sector"),
    "Mercado de Cambios": ("mc", "Mercado de cambios"),
    "Anexo tarjetas y viajes": ("tv", "Tarjetas, viajes y pasajes"),
}
es_codigo = lambda v: isinstance(v, str) and re.fullmatch(r"[a-z]{2,8}\d{3,4}", v.strip()) is not None  # noqa: E731


def limpiar(txt):
    txt = re.sub(r"\s+", " ", str(txt)).strip()
    txt = re.sub(r"\s*\(\d+\)$", "", txt)  # notas al pie: "(3)"
    return txt[:1].upper() + txt[1:].lower() if txt.isupper() else txt


def leer(contenido):
    series = {}
    for hoja, (prefijo, categoria) in HOJAS.items():
        d = pd.read_excel(io.BytesIO(contenido), sheet_name=hoja, header=None)
        fila = next((i for i in range(min(40, len(d))) if sum(es_codigo(v) for v in d.iloc[i]) >= 3), None)
        if fila is None:
            continue
        enc = d.iloc[4:fila].astype(object).ffill(axis=1).infer_objects()  # celdas combinadas hacia la derecha
        mensual = d.iloc[fila + 1:]
        mensual = mensual[mensual[0].map(lambda v: isinstance(v, dt.datetime))]  # descarta totales anuales
        nombres_hoja = {}
        for c in range(1, d.shape[1]):
            cod = d.iloc[fila, c]
            if not es_codigo(cod) or f"bcra_{prefijo}_{cod.strip()}" in series:
                continue
            partes = []
            for v in enc[c]:
                v = limpiar(v) if pd.notna(v) else ""
                if v and v.lower() not in ("mes",) and v not in partes:
                    partes.append(v)
            nombre = " › ".join(partes) or cod
            if " › " not in nombre:  # p. ej. "Total": se aclara de qué sección es
                nombre = f"{categoria}: {nombre.lower()}"
            if nombre in nombres_hoja.values():
                nombre += f" ({cod.strip()})"
            s = pd.Series(pd.to_numeric(mensual[c], errors="coerce").values,
                          index=pd.to_datetime(mensual[0].tolist())).dropna()
            if len(s):
                sid = f"bcra_{prefijo}_{cod.strip()}"
                nombres_hoja[sid] = nombre
                series[sid] = (s, nombre, categoria, hoja, cod.strip())
    return series


def coincide(nuevas, viejas):
    for sid in ("bcra_bc_bal003", "bcra_bc_bal004", "bcra_bc_bal001"):
        if sid in nuevas and sid in viejas:
            n, v = nuevas[sid][0], viejas[sid][0]
            comunes = n.index.intersection(v.index)
            comunes = comunes[comunes <= v.index.max() - pd.DateOffset(months=6)]
            if len(comunes) < 24:
                return False
            base = v[comunes].abs().replace(0, pd.NA).dropna()
            return ((n[base.index] - v[base.index]).abs() / base).median() < 0.01
    return False


def main():
    actual = leer(ARCHIVO.read_bytes())
    for url in URLS:
        try:
            r = requests.get(url, timeout=120, headers={"User-Agent": "Mozilla/5.0"})
        except requests.RequestException:
            continue
        if r.ok and r.content[:2] == b"PK":
            try:
                nuevas = leer(r.content)
            except Exception:  # noqa: BLE001
                continue
            if coincide(nuevas, actual):
                ARCHIVO.write_bytes(r.content)
                actual = nuevas
                print(f"Archivo nuevo del BCRA validado ({url})")
                break
            print(f"::warning::Balance cambiario: el archivo de {url} no coincide con la historia; no se usa.")
    else:
        print("::warning::Balance cambiario: no se pudo bajar el archivo nuevo del BCRA; se usa el del repo.")

    metas, obs = [], []
    for sid, (s, nombre, categoria, hoja, cod) in actual.items():
        metas.append({"id": sid, "nombre": nombre, "fuente": "BCRA", "categoria": categoria,
                      "unidad": "Millones de USD", "frecuencia": "M", "id_api_bcra": None,
                      "archivo_origen": "src/bcra/balance_cambiario.py",
                      "descripcion": f"Anexo estadístico del balance cambiario del BCRA, hoja '{hoja}', columna {cod}. "
                                     "Operaciones del mercado de cambios en millones de dólares."})
        obs.append(pd.DataFrame({"serie_id": sid, "fecha": s.index.strftime("%Y-%m-%d"), "valor": s.values}))
    SALIDA.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(metas).astype({"id_api_bcra": "Int64"}).to_csv(SALIDA / "series.csv", index=False)
    pd.concat(obs).to_csv(SALIDA / "observaciones.csv", index=False)
    ultimo = max(s.index.max() for s, *_ in actual.values())
    print(f"Balance cambiario: {len(metas)} series mensuales, hasta {ultimo:%Y-%m}")


if __name__ == "__main__":
    main()
