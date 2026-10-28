"""Publica TODAS las series en datos/, un archivo CSV por serie (fecha, valor), organizadas por
fuente y tema, con un índice general (datos/INDICE.csv) y un README por carpeta.

datos/ es la única copia versionada de las series: data/processed/ es un área de trabajo interna.
Cualquier fuente nueva que escriba data/processed/<fuente>/series.csv + observaciones.csv durante la
corrida aparece sola en datos/.

Uso: python src/exportar_archivos.py
"""
import os
import re
import shutil
import sys
import unicodedata
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
PROCESSED = RAIZ / "data" / "processed"
DESTINO = RAIZ / "datos"
FRECUENCIAS = {"D": "Diaria", "M": "Mensual", "T": "Trimestral", "S": "Semestral", "A": "Anual"}
CARPETA_FUENTE = {  # nombre de carpeta por fuente (lo que no está acá se arma solo con el nombre)
    "Club de Economía UADE (elaboración propia)": "elaboracion_propia_club",
    "ArgentinaDatos (no oficial)": "mercados_argentinadatos",
    "ANSES / Secretaría de Seguridad Social": "anses",
    "Secretaría de Hacienda (IMIG)": "secretaria_de_hacienda",
    "Secretaría de Trabajo (SIPA)": "secretaria_de_trabajo",
    "BCRA (REM)": "bcra",
    "Universidad Torcuato Di Tella (ICG), vía opinAr": "utdt_confianza_en_el_gobierno",
    "FRED (Reserva Federal de St. Louis)": "fred_estados_unidos_y_commodities",
    "Banco Central de Brasil": "brasil_banco_central",
    "FMI": "fmi",
    "Proyecto Maddison": "proyecto_maddison",
    "Secretaría de Energía": "secretaria_de_energia",
    "Ministerio de Agricultura": "ministerio_de_agricultura",
}


def slug(txt, largo=90):
    s = unicodedata.normalize("NFD", str(txt).lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s[:largo].rstrip("_")


def nombre_corto(nombre):
    """Nombre para el archivo: sin el paréntesis final (unidades, bases, meses que cambian)."""
    return re.sub(r"\s*\([^()]*\)\s*$", "", str(nombre)).strip() or str(nombre)


def cargar():
    """Junta las series de tres orígenes, en este orden de prioridad:
    1. lo que produjo esta corrida en data/processed/<fuente>/;
    2. la base de datos (fuentes que van a la página), si hay credenciales: incluye lo que llegó por API;
    3. la versión ya publicada en datos/, para las series que no se actualizaron en esta corrida.
    """
    usa_base = bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY"))
    sys.path.insert(0, str(RAIZ / "src"))
    from almacen import COLUMNAS_META, FREQ_CODIGO, SOLO_REPO
    if usa_base:
        from supabase_db import _config, leer_serie
    metas, datos = {}, {}

    # 1 y 2: fuentes con archivos de esta corrida
    for carpeta in sorted(p.parent for p in PROCESSED.glob("*/series.csv")):
        series = pd.read_csv(carpeta / "series.csv")
        local = {}
        if (carpeta / "observaciones.csv").exists():
            local = {k: g for k, g in pd.read_csv(carpeta / "observaciones.csv").groupby("serie_id")}
        for _, m in series.iterrows():
            if usa_base and carpeta.name not in SOLO_REPO:
                df = pd.DataFrame(leer_serie(m["id"]))
            else:
                df = local.get(m["id"], pd.DataFrame())
            if not df.empty:
                datos[m["id"]] = df[["fecha", "valor"]]
                metas[m["id"]] = {**{k: m.get(k) for k in COLUMNAS_META}, "carpeta_origen": carpeta.name}

    # 2: el resto de la base (p. ej. el BCRA, que en las corridas semanales llega solo por API)
    if usa_base:
        import requests
        base, headers = _config()
        r = requests.get(f"{base}/series", headers=headers, params={"select": "*"}, timeout=60)
        r.raise_for_status()
        anterior = pd.read_csv(DESTINO / "INDICE.csv") if (DESTINO / "INDICE.csv").exists() else pd.DataFrame()
        carpeta_de = dict(zip(anterior.get("id", []), anterior.get("carpeta_origen", [])))
        from concurrent.futures import ThreadPoolExecutor
        pendientes = [m for m in r.json() if m["id"] not in metas]
        with ThreadPoolExecutor(max_workers=8) as ex:  # en paralelo: de a una tardaba varios minutos
            leidas = list(ex.map(lambda m: pd.DataFrame(leer_serie(m["id"])), pendientes))
        for m, df in zip(pendientes, leidas):
            if not df.empty:
                datos[m["id"]] = df[["fecha", "valor"]]
                metas[m["id"]] = {**{k: m.get(k) for k in COLUMNAS_META},
                                  "carpeta_origen": carpeta_de.get(m["id"], "base")}

    # 3: series publicadas que no se actualizaron en esta corrida (su fuente falló o no corrió)
    conservadas = 0
    if (DESTINO / "INDICE.csv").exists():
        anterior = pd.read_csv(DESTINO / "INDICE.csv")
        for _, f in anterior.iterrows():
            if f["id"] in metas or not (DESTINO / f["archivo"]).exists():
                continue
            datos[f["id"]] = pd.read_csv(DESTINO / f["archivo"])
            metas[f["id"]] = {"id": f["id"], "nombre": f["serie"], "fuente": f["fuente"], "categoria": f["tema"],
                              "unidad": f["unidad"], "frecuencia": FREQ_CODIGO.get(f["frecuencia"], f["frecuencia"]),
                              "id_api_bcra": f.get("id_api_bcra"), "archivo_origen": f.get("archivo_origen"),
                              "descripcion": f.get("descripcion"), "carpeta_origen": f.get("carpeta_origen", "base")}
            conservadas += 1
    for sid in datos:
        datos[sid] = datos[sid].sort_values("fecha").drop_duplicates("fecha", keep="last")
    print(f"{len(metas)} series ({'base + corrida' if usa_base else 'archivos locales'}; "
          f"{conservadas} conservadas de la versión publicada)")
    return pd.DataFrame(list(metas.values())), datos


def main():
    from almacen import SOLO_REPO
    metas, datos = cargar()
    if metas.empty:
        print("::warning::No hay series para exportar; no se modifica datos/.")
        return
    previo = DESTINO / "INDICE.csv"
    if previo.exists():
        antes = len(pd.read_csv(previo))
        if len(metas) < 0.9 * antes:  # protección: una lectura incompleta no puede borrar archivos
            print(f"::warning::Se obtuvieron {len(metas)} series y había {antes}; no se modifica datos/.")
            return
    if DESTINO.exists():
        shutil.rmtree(DESTINO)  # se regenera completa: si una serie se renombra no quedan archivos viejos
    indice, usados = [], set()
    for _, m in metas.sort_values(["fuente", "categoria", "nombre"]).iterrows():
        fuente_dir = CARPETA_FUENTE.get(m["fuente"], slug(m["fuente"], 40))
        ruta = Path(fuente_dir) / slug(m.get("categoria") or "otros", 40)
        archivo = ruta / f"{slug(nombre_corto(m['nombre']))}.csv"
        if archivo in usados:  # nombres repetidos: se agrega el id
            archivo = ruta / f"{slug(nombre_corto(m['nombre']), 70)}__{m['id']}.csv"
        usados.add(archivo)
        (DESTINO / ruta).mkdir(parents=True, exist_ok=True)
        df = datos[m["id"]]
        df.to_csv(DESTINO / archivo, index=False)
        indice.append({"archivo": archivo.as_posix(), "serie": m["nombre"], "fuente": m["fuente"],
                       "tema": m.get("categoria"), "unidad": m.get("unidad"),
                       "frecuencia": FRECUENCIAS.get(m.get("frecuencia"), m.get("frecuencia")),
                       "desde": str(df["fecha"].iloc[0])[:10], "hasta": str(df["fecha"].iloc[-1])[:10],
                       "datos": len(df), "id": m["id"],
                       "en_la_pagina": "no" if m["carpeta_origen"] in SOLO_REPO else "sí",
                       "descripcion": m.get("descripcion") if isinstance(m.get("descripcion"), str) else "",
                       "carpeta_origen": m["carpeta_origen"],
                       "id_api_bcra": m.get("id_api_bcra") if pd.notna(m.get("id_api_bcra")) else "",
                       "archivo_origen": m.get("archivo_origen") if isinstance(m.get("archivo_origen"), str) else ""})
    ind = pd.DataFrame(indice)
    ind.to_csv(DESTINO / "INDICE.csv", index=False)

    # README general (GitHub lo muestra al entrar a datos/) y uno por fuente
    ind["carpeta"] = ind["archivo"].str.split("/").str[0]
    total_datos = int(ind["datos"].sum())
    lineas = ["# Datos del Club de Economía UADE", "",
              f"**{len(ind):,} series** y **{total_datos:,} datos**".replace(",", ".") +
              ", un archivo CSV por serie (`fecha, valor`), listos para abrir en Excel o Google Sheets. "
              "Se actualizan solos todas las semanas.", "",
              "El detalle de cada serie (unidad, período, fuente y cómo se construye) está en "
              "[`INDICE.csv`](INDICE.csv). De dónde sale cada fuente y cómo se valida: "
              "[`docs/FUENTES.md`](../docs/FUENTES.md). Cómo se calculan las series propias: "
              "[`docs/METODOLOGIA.md`](../docs/METODOLOGIA.md).", "",
              "Esta carpeta se genera automáticamente; no editar a mano.", "", "| Fuente | Series | Temas | Desde | Hasta |", "|---|---|---|---|---|"]
    for carpeta, g in ind.groupby("carpeta"):
        temas = ", ".join(sorted(g["tema"].dropna().unique()))
        hasta = g["hasta"].max()[:4] if (g["frecuencia"] == "Anual").all() else g["hasta"].max()[:7]
        lineas.append(f"| [{g['fuente'].iloc[0]}]({carpeta}/) | {len(g)} | {temas} | {g['desde'].min()[:4]} | {hasta} |")
        sub = [f"# {g['fuente'].iloc[0]}", "", f"{len(g)} series.", ""]
        for tema, t in g.groupby("tema"):
            sub += [f"## {tema}", "", "| Serie | Unidad | Frecuencia | Desde | Hasta |", "|---|---|---|---|---|"]
            for _, r in t.iterrows():
                rel = r["archivo"].split("/", 1)[1]
                sub.append(f"| [{r['serie']}]({rel}) | {r['unidad']} | {r['frecuencia']} | {r['desde']} | {r['hasta']} |")
            sub.append("")
        (DESTINO / carpeta / "README.md").write_text("\n".join(sub) + "\n", encoding="utf-8")
    (DESTINO / "README.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"-> {len(ind)} archivos en datos/ ({ind['carpeta'].nunique()} fuentes, {total_datos:,} datos)")


if __name__ == "__main__":
    main()
