"""Trae las series de src/datos_gob/catalogo.py; se publican en datos/ (no se suben a la base).

No se cargan en Supabase ni se muestran en la página (cargar_supabase.py las excluye por defecto).

Por cada serie:
  1. Pide el ID a la API y verifica, con los metadatos que devuelve, que sea la serie esperada.
  2. Si el ID no existe o no coincide, la busca por texto: solo acepta si hay UN candidato que
     cumple las palabras clave y la frecuencia. Si hay varios, no carga y los lista en el aviso.
  3. Compara contra lo ya guardado: si la historia cambió mucho (ID que pasó a ser otra serie), no la pisa.
  4. Avisa si el último dato es demasiado viejo (serie "congelada" en la API).

Uso: python src/datos_gob/actualizar.py
"""
import io
import re
import sys
import time
import unicodedata
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalogo import CSV_SALARIOS, SERIES  # noqa: E402

API = "https://apis.datos.gob.ar/series/api"
RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "data" / "processed" / "datos_gob"
RAW = RAIZ / "data" / "raw" / "datos_gob"  # un CSV por serie, para abrir directo en Excel
FREQ = {"R/P1M": "M", "R/P3M": "T", "R/P1Y": "A"}
TOLERANCIA_HISTORIA = 0.05  # 5%: mediana de diferencia relativa admitida contra lo ya guardado
sesion = requests.Session()
sesion.headers["User-Agent"] = "club-economia-uade/1.0"


ACTUAL = {"sid": None}   # serie que se está procesando (para el reporte)
NOTAS = {}               # sid -> lista de mensajes de esta corrida


def nota(msg):
    NOTAS.setdefault(ACTUAL["sid"], []).append(msg)
    print(f"  {ACTUAL['sid']}: {msg}")


def aviso(msg):
    NOTAS.setdefault(ACTUAL["sid"], []).append(msg)
    print(f"::warning::{msg}")


def norm(x):
    s = unicodedata.normalize("NFD", str(x or "").replace("_", " ").lower())
    return re.sub(r"\s+", " ", "".join(c for c in s if unicodedata.category(c) != "Mn"))


def coincide(spec, texto):
    t = norm(texto)
    if spec.get("exacto") and not re.search(spec["exacto"], t):
        return False
    ok = all(any(norm(a) in t for a in (k if isinstance(k, tuple) else (k,))) for k in spec["kw"])
    return ok and not any(norm(k) in t for k in spec.get("kw_not", []))


def get(ruta, params, intentos=3):
    time.sleep(0.3)  # no saturar la API (los cortes momentáneos dejaban series afuera)
    for intento in range(intentos):
        try:
            r = sesion.get(f"{API}/{ruta}", params=params, timeout=30)
        except requests.RequestException:
            time.sleep(2 ** intento)
            continue
        if r.status_code == 200:
            return r.json()
        if r.status_code == 404:
            return None
        time.sleep(2 * (intento + 1))
    return None


def serie_api(id_api, texto_busqueda=None):
    js = get("series/", {"ids": id_api, "format": "json", "metadata": "full", "limit": 5000, "sort": "asc"})
    if (not js or not js.get("data")) and texto_busqueda:
        # algunas series fallan al pedir metadatos completos; la búsqueda ya confirmó cuál es
        for params in ({"metadata": "none", "limit": 5000}, {"metadata": "simple", "limit": 1000}, {"limit": 1000}):
            js = get("series/", {"ids": id_api, "format": "json", "sort": "asc", **params}, intentos=2)
            if js and js.get("data"):
                js["meta"] = [{}, {"field": {"description": texto_busqueda}, "dataset": {}}]
                break
    if not js or not js.get("data"):
        return None
    meta = next((m for m in js.get("meta", []) if isinstance(m, dict) and "field" in m), {})
    campo, dataset = meta.get("field", {}), meta.get("dataset", {})
    df = pd.DataFrame(js["data"], columns=["fecha", "valor"])
    s = pd.Series(pd.to_numeric(df["valor"], errors="coerce").values, index=pd.to_datetime(df["fecha"])).dropna()
    texto = " | ".join(str(x) for x in [campo.get("description"), campo.get("title"), dataset.get("title")] if x)
    return {"id": id_api, "texto": texto, "freq": FREQ.get(campo.get("frequency")), "s": s,
            "unidad": campo.get("units")}


def resolver(spec):
    if spec.get("id"):
        got = serie_api(spec["id"])
        if got and coincide(spec, got["texto"]) and got["freq"] in (None, spec["freq"]):
            return got
        motivo = "no existe" if not got else f"la API la describe como '{got['texto'][:90]}'"
        nota(f"el ID {spec['id']} {motivo}; busco por texto")
    if not spec.get("q"):
        return None
    candidatos = {}
    consultas = spec["q"] if isinstance(spec["q"], list) else [spec["q"]]
    hits = [h for q in consultas for h in (get("search/", {"q": q, "limit": 100}) or {}).get("data", [])]
    for h in hits:
        campo, dataset = h.get("field", {}), h.get("dataset", {})
        texto = f"{campo.get('description', '')} | {campo.get('title', '')} | {dataset.get('title', '')}"
        if coincide(spec, texto) and FREQ.get(campo.get("frequency")) in (None, spec["freq"]):
            candidatos[campo.get("id")] = texto
    if spec.get("id") in candidatos:  # el ID configurado aparece en la búsqueda: era un corte momentáneo
        got = serie_api(spec["id"], candidatos[spec["id"]])
        if got is not None:
            nota(f"el ID {spec['id']} respondió al reintentar")
            return got
    if len(candidatos) == 1:
        id_api = next(iter(candidatos))
        nota(f"resuelta por texto -> {id_api} ({candidatos[id_api][:90]})")
        return serie_api(id_api, candidatos[id_api])
    lista = "; ".join(f"{k}: {v[:60]}" for k, v in list(candidatos.items())[:6]) or "ninguno"
    aviso(f"{spec['sid']}: no se pudo identificar la serie en la API ({len(candidatos)} candidatos: {lista}). "
          "Fijar el ID correcto en src/datos_gob/catalogo.py.")
    return None


def slug(txt):
    txt = norm(txt)
    return re.sub(r"[^a-z0-9]+", "_", txt).strip("_")


def salarios_csv():
    """Lee el CSV del INDEC; devuelve {columna: pd.Series} o {} si no está disponible."""
    try:
        r = sesion.get(CSV_SALARIOS, timeout=60)
        if not r.ok or b";" not in r.content[:500]:
            return {}
        original = RAIZ / "data" / "raw" / "indec" / "salarios" / "indice_salarios.csv"
        original.parent.mkdir(parents=True, exist_ok=True)
        original.write_bytes(r.content)  # el archivo tal cual lo publica el INDEC
        df = pd.read_csv(io.StringIO(r.content.decode("utf-8-sig")), sep=";", decimal=",", na_values=["NA", ""])
        fechas = pd.to_datetime(df["periodo"], format="%d/%m/%Y", errors="coerce")
        return {c: pd.Series(pd.to_numeric(df[c], errors="coerce").values, index=fechas).dropna()
                for c in df.columns if c.startswith("IS_")}
    except Exception as e:  # noqa: BLE001
        aviso(f"Índice de salarios: no se pudo leer el CSV del INDEC ({e}); se usa la API.")
        return {}


def historia_cambio(nueva, anterior):
    comunes = nueva.index.intersection(anterior.index)
    comunes = comunes[comunes <= anterior.index.max() - pd.DateOffset(months=6)]  # lo reciente se revisa
    if len(comunes) < 12:
        return None
    a = anterior[comunes].replace(0, pd.NA).dropna()
    dif = ((nueva[a.index] / a - 1).abs()).median()
    return dif if dif > TOLERANCIA_HISTORIA else None


def main():
    sys.path.insert(0, str(RAIZ / "src"))
    from almacen import observaciones
    o = observaciones("datos_gob")
    o["fecha"] = pd.to_datetime(o["fecha"])
    previas = {k: g.set_index("fecha")["valor"] for k, g in o.groupby("serie_id")}
    # chequeo rápido: si la API no responde, no tiene sentido recorrer las 30 series
    if get("series/", {"ids": "143.3_NO_PR_2004_A_21", "limit": 1, "format": "json"}, intentos=2) is None:
        aviso("datos.gob.ar no responde; se mantienen los datos anteriores.")
        return
    csv = salarios_csv()
    metas, obs, ok, reporte, calculadas = [], [], 0, [], {}
    for spec in SERIES:
        ACTUAL["sid"] = spec["sid"]
        origen = None
        if spec.get("csv") and not csv.get(spec["csv"], pd.Series(dtype=float)).empty:
            s, origen = csv[spec["csv"]], f"CSV INDEC ({CSV_SALARIOS}), columna {spec['csv']}"
        else:
            got = resolver(spec)
            if got is not None:
                s, origen = got["s"], f"API Series de Tiempo, ID {got['id']} ({got['texto'][:120]})"
                if spec["unidad"] == "Ver descripción" and got.get("unidad"):
                    spec = {**spec, "unidad": str(got["unidad"])}
        if origen is None and spec.get("calculo"):
            a, op, b = spec["calculo"]
            sa, sb = calculadas.get(a), calculadas.get(b)
            if sa is not None and sb is not None:
                s = (sa - sb if op == "-" else sa + sb).dropna()
                origen = f"calculada: {a} {op} {b} (la API no publica la serie)"
                nota(origen)
        if origen is None:
            if spec["sid"] in previas:  # se conserva lo que había
                s, origen = previas[spec["sid"]], "sin actualizar en esta corrida (se conserva el dato anterior)"
            else:
                reporte.append({"serie": spec["sid"], "estado": "FALTA", "origen": "", "desde": "", "hasta": "",
                                "notas": " | ".join(NOTAS.get(spec["sid"], ["sin datos"]))})
                continue
        if spec.get("desde"):
            s = s[s.index >= pd.Timestamp(spec["desde"])]
        if s.empty:
            aviso(f"{spec['sid']}: la fuente no devolvió datos.")
            reporte.append({"serie": spec["sid"], "estado": "FALTA", "origen": origen, "desde": "", "hasta": "",
                            "notas": " | ".join(NOTAS.get(spec["sid"], []))})
            continue
        if spec.get("desde") and s.index.min() > pd.Timestamp(spec["desde"]) + pd.DateOffset(years=2):
            aviso(f"{spec['sid']}: la serie empieza en {s.index.min():%Y-%m}, se esperaba desde {spec['desde'][:7]}. "
                  "La API puede estar devolviendo un tramo incompleto.")
        if spec["sid"] in previas and not origen.startswith("sin actualizar"):
            dif = historia_cambio(s, previas[spec["sid"]])
            if dif is not None:
                aviso(f"{spec['sid']}: la historia difiere {dif:.1%} de la guardada; puede ser otra serie. "
                      "Se conserva la anterior.")
                s, origen = previas[spec["sid"]], "sin actualizar: la fuente no coincidió con la historia guardada"
        hoy = pd.Timestamp.today().normalize()
        ultimo = s.index.max()
        fin_periodo = ultimo + pd.DateOffset(months={"M": 1, "T": 3, "S": 6, "A": 12}.get(spec["freq"], 1))
        if ultimo <= hoy and (hoy - fin_periodo).days > spec["dias"]:
            aviso(f"{spec['sid']}: último dato {ultimo:%Y-%m}; el período cerró hace {(hoy - fin_periodo).days} días. "
                  "La fuente puede estar congelada.")
        descripcion = f"Fuente: {spec['fuente']}. Origen del dato: {origen}."
        if spec.get("nota"):
            descripcion += " " + spec["nota"]
        metas.append({"id": spec["sid"], "nombre": spec["nombre"], "fuente": spec["fuente"],
                      "categoria": spec["categoria"], "unidad": spec["unidad"], "frecuencia": spec["freq"],
                      "id_api_bcra": None, "archivo_origen": "src/datos_gob/actualizar.py", "descripcion": descripcion})
        obs.append(pd.DataFrame({"serie_id": spec["sid"], "fecha": s.index.strftime("%Y-%m-%d"), "valor": s.values}))
        ok += 1
        calculadas[spec["sid"]] = s
        estado = "OK" if not origen.startswith("sin actualizar") else "CONSERVADA"
        if any("cerró hace" in n for n in NOTAS.get(spec["sid"], [])):
            estado += " (atrasada)"
        reporte.append({"serie": spec["sid"], "estado": estado, "origen": origen, "desde": f"{s.index.min():%Y-%m}",
                        "hasta": f"{ultimo:%Y-%m}", "notas": " | ".join(NOTAS.get(spec["sid"], []))})
        print(f"[ok] {spec['sid']}: {len(s)} datos, {s.index.min():%Y-%m} a {ultimo:%Y-%m} · {origen[:70]}")

    RAW.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(reporte).to_csv(RAW / "ESTADO.csv", index=False)  # qué pasó con cada serie en esta corrida
    if not obs:
        aviso("datos.gob.ar: no se obtuvo ninguna serie; no se modifican los archivos.")
        return
    SALIDA.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(metas).astype({"id_api_bcra": "Int64"}).to_csv(SALIDA / "series.csv", index=False)
    pd.concat(obs).to_csv(SALIDA / "observaciones.csv", index=False)

    # data/raw/datos_gob/<categoría>/<serie>.csv (fecha, valor) + INDICE.csv
    indice = []
    for m, o in zip(metas, obs):
        carpeta = RAW / slug(m["categoria"])
        carpeta.mkdir(parents=True, exist_ok=True)
        archivo = carpeta / f"{m['id']}.csv"
        o[["fecha", "valor"]].to_csv(archivo, index=False)
        indice.append({"archivo": str(archivo.relative_to(RAW)), "serie": m["nombre"], "unidad": m["unidad"],
                       "frecuencia": m["frecuencia"], "desde": o["fecha"].min(), "hasta": o["fecha"].max(),
                       "fuente": m["fuente"], "detalle": m["descripcion"]})
    pd.DataFrame(indice).to_csv(RAW / "INDICE.csv", index=False)
    print(f"-> {ok} de {len(SERIES)} series")


if __name__ == "__main__":
    main()
