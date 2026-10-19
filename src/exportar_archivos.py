"""Exporta TODAS las series del repo a datos/, un archivo CSV por serie (fecha, valor),
organizadas por fuente y tema, con un índice general y un README por carpeta.

Fuente de cada serie:
  - carpetas de data/processed/ que van a la base: de Supabase si hay credenciales (lo más
    actualizado, incluye lo que llega por API), si no del CSV local;
  - carpetas marcadas .solo_repo: siempre del CSV local.
Cualquier fuente nueva que escriba data/processed/<fuente>/series.csv + observaciones.csv
aparece sola en datos/.

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
    usa_base = bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY"))
    if usa_base:
        sys.path.insert(0, str(RAIZ / "src"))
        from supabase_db import leer_serie
    metas, datos = [], {}
    for carpeta in sorted(p.parent for p in PROCESSED.glob("*/series.csv")):
        series = pd.read_csv(carpeta / "series.csv")
        solo_repo = (carpeta / ".solo_repo").exists()
        local = None
        if (carpeta / "observaciones.csv").exists():
            local = {k: g for k, g in pd.read_csv(carpeta / "observaciones.csv").groupby("serie_id")}
        for _, m in series.iterrows():
            if usa_base and not solo_repo:
                df = pd.DataFrame(leer_serie(m["id"]))
            elif local is not None and m["id"] in local:
                df = local[m["id"]]
            else:
                continue
            if df.empty:
                continue
            datos[m["id"]] = df[["fecha", "valor"]].sort_values("fecha").drop_duplicates("fecha", keep="last")
            metas.append({**m.to_dict(), "carpeta_origen": carpeta.name})
    print(f"{len(metas)} series ({'Supabase + repo' if usa_base else 'CSV locales'})")
    return pd.DataFrame(metas), datos


def main():
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
                       "datos": len(df), "id": m["id"], "en_la_pagina": "no" if m["carpeta_origen"] in
                       {p.parent.name for p in PROCESSED.glob("*/.solo_repo")} else "sí",
                       "descripcion": m.get("descripcion") if isinstance(m.get("descripcion"), str) else ""})
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
