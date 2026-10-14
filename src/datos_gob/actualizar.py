"""Trae las series de src/datos_gob/catalogo.py y las guarda en data/processed/datos_gob/.

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
FREQ = {"R/P1M": "M", "R/P3M": "T", "R/P1Y": "A"}
TOLERANCIA_HISTORIA = 0.05  # 5%: mediana de diferencia relativa admitida contra lo ya guardado
sesion = requests.Session()
sesion.headers["User-Agent"] = "club-economia-uade/1.0"


def aviso(msg):
    print(f"::warning::{msg}")


def norm(x):
    s = unicodedata.normalize("NFD", str(x or "").replace("_", " ").lower())
    return re.sub(r"\s+", " ", "".join(c for c in s if unicodedata.category(c) != "Mn"))


def coincide(spec, texto):
    t = norm(texto)
    ok = all(any(norm(a) in t for a in (k if isinstance(k, tuple) else (k,))) for k in spec["kw"])
    return ok and not any(norm(k) in t for k in spec.get("kw_not", []))


def get(ruta, params):
    for intento in range(4):
        try:
            r = sesion.get(f"{API}/{ruta}", params=params, timeout=60)
        except requests.RequestException:
            time.sleep(2 ** intento)
            continue
        if r.status_code == 200:
            return r.json()
        if r.status_code in (400, 404):
            return None
        time.sleep(2 ** intento)
    return None


def serie_api(id_api):
    js = get("series/", {"ids": id_api, "format": "json", "metadata": "full", "limit": 5000, "sort": "asc"})
    if not js or not js.get("data"):
        return None
    meta = next((m for m in js.get("meta", []) if isinstance(m, dict) and "field" in m), {})
    campo, dataset = meta.get("field", {}), meta.get("dataset", {})
    df = pd.DataFrame(js["data"], columns=["fecha", "valor"])
    s = pd.Series(pd.to_numeric(df["valor"], errors="coerce").values, index=pd.to_datetime(df["fecha"])).dropna()
    texto = " | ".join(str(x) for x in [campo.get("description"), campo.get("title"), dataset.get("title")] if x)
    return {"id": id_api, "texto": texto, "freq": FREQ.get(campo.get("frequency")), "s": s}


def resolver(spec):
    if spec.get("id"):
        got = serie_api(spec["id"])
        if got and coincide(spec, got["texto"]) and got["freq"] in (None, spec["freq"]):
            return got
        motivo = "no existe" if not got else f"la API la describe como '{got['texto'][:90]}'"
        print(f"  {spec['sid']}: el ID {spec['id']} {motivo}; busco por texto")
    if not spec.get("q"):
        return None
    candidatos = {}
    for h in (get("search/", {"q": spec["q"], "limit": 50}) or {}).get("data", []):
        campo, dataset = h.get("field", {}), h.get("dataset", {})
        texto = f"{campo.get('description', '')} | {campo.get('title', '')} | {dataset.get('title', '')}"
        if coincide(spec, texto) and FREQ.get(campo.get("frequency")) in (None, spec["freq"]):
            candidatos[campo.get("id")] = texto
    if len(candidatos) == 1:
        id_api = next(iter(candidatos))
        print(f"  {spec['sid']}: resuelta por texto -> {id_api} ({candidatos[id_api][:90]})")
        return serie_api(id_api)
    lista = "; ".join(f"{k}: {v[:60]}" for k, v in list(candidatos.items())[:6]) or "ninguno"
    aviso(f"{spec['sid']}: no se pudo identificar la serie en la API ({len(candidatos)} candidatos: {lista}). "
          "Fijar el ID correcto en src/datos_gob/catalogo.py.")
    return None


def salarios_csv():
    """Lee el CSV del INDEC; devuelve {columna: pd.Series} o {} si no está disponible."""
    try:
        r = sesion.get(CSV_SALARIOS, timeout=60)
        if not r.ok or b";" not in r.content[:500]:
            return {}
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
    previas = {}
    if (SALIDA / "observaciones.csv").exists():
        o = pd.read_csv(SALIDA / "observaciones.csv", parse_dates=["fecha"])
        previas = {k: g.set_index("fecha")["valor"] for k, g in o.groupby("serie_id")}
    csv = salarios_csv()
    metas, obs, ok = [], [], 0
    for spec in SERIES:
        origen = None
        if spec.get("csv") and not csv.get(spec["csv"], pd.Series(dtype=float)).empty:
            s, origen = csv[spec["csv"]], f"CSV INDEC ({CSV_SALARIOS}), columna {spec['csv']}"
        else:
            got = resolver(spec)
            if got is not None:
                s, origen = got["s"], f"API Series de Tiempo, ID {got['id']} ({got['texto'][:120]})"
        if origen is None:
            if spec["sid"] in previas:  # se conserva lo que había
                s, origen = previas[spec["sid"]], "sin actualizar en esta corrida (se conserva el dato anterior)"
            else:
                continue
        if spec.get("desde"):
            s = s[s.index >= pd.Timestamp(spec["desde"])]
        if s.empty:
            aviso(f"{spec['sid']}: la fuente no devolvió datos.")
            continue
        if spec["sid"] in previas and not origen.startswith("sin actualizar"):
            dif = historia_cambio(s, previas[spec["sid"]])
            if dif is not None:
                aviso(f"{spec['sid']}: la historia difiere {dif:.1%} de la guardada; puede ser otra serie. "
                      "Se conserva la anterior.")
                s, origen = previas[spec["sid"]], "sin actualizar: la fuente no coincidió con la historia guardada"
        hoy = pd.Timestamp.today().normalize()
        ultimo = s.index.max()
        if ultimo <= hoy and (hoy - ultimo).days > spec["dias"]:
            aviso(f"{spec['sid']}: último dato {ultimo:%Y-%m}, hace {(hoy - ultimo).days} días. "
                  "La fuente puede estar congelada.")
        descripcion = f"Fuente: {spec['fuente']}. Origen del dato: {origen}."
        if spec.get("nota"):
            descripcion += " " + spec["nota"]
        metas.append({"id": spec["sid"], "nombre": spec["nombre"], "fuente": spec["fuente"],
                      "categoria": spec["categoria"], "unidad": spec["unidad"], "frecuencia": spec["freq"],
                      "id_api_bcra": None, "archivo_origen": "src/datos_gob/actualizar.py", "descripcion": descripcion})
        obs.append(pd.DataFrame({"serie_id": spec["sid"], "fecha": s.index.strftime("%Y-%m-%d"), "valor": s.values}))
        ok += 1
        print(f"[ok] {spec['sid']}: {len(s)} datos, {s.index.min():%Y-%m} a {ultimo:%Y-%m} · {origen[:70]}")

    if not obs:
        aviso("datos.gob.ar: no se obtuvo ninguna serie; no se modifican los archivos.")
        return
    SALIDA.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(metas).astype({"id_api_bcra": "Int64"}).to_csv(SALIDA / "series.csv", index=False)
    pd.concat(obs).to_csv(SALIDA / "observaciones.csv", index=False)
    print(f"-> {ok} de {len(SERIES)} series guardadas en data/processed/datos_gob/")


if __name__ == "__main__":
    main()
