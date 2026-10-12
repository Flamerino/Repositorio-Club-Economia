"""Acceso a datos para la app: lee de Supabase (o de los CSV locales en modo desarrollo)."""
import os
import re
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

# Clave publishable: solo permite LEER (la escritura está bloqueada por RLS).
# Se puede sobrescribir con st.secrets o variables de entorno.
URL_DEFECTO = "https://opnfzrzleftioaafkqua.supabase.co"
CLAVE_DEFECTO = "sb_publishable_pOxPr87EoSaByshuFYf-aw_wkESBC5x"

PAGINA = 1000  # Supabase devuelve como máximo 1000 filas por consulta
CACHE = 6 * 60 * 60
RAIZ = Path(__file__).resolve().parents[1]
LOCAL = os.environ.get("DATOS_LOCALES") == "1"  # desarrollo sin conexión: lee data/processed/


def _config():
    try:
        url = st.secrets.get("SUPABASE_URL", URL_DEFECTO)
        clave = st.secrets.get("SUPABASE_ANON_KEY", CLAVE_DEFECTO)
    except Exception:  # noqa: BLE001  (no hay secrets.toml)
        url = os.environ.get("SUPABASE_URL", URL_DEFECTO)
        clave = os.environ.get("SUPABASE_ANON_KEY", CLAVE_DEFECTO)
    url = url.strip().rstrip("/").removesuffix("/rest/v1")
    headers = {"apikey": clave}
    if clave.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {clave}"
    return url + "/rest/v1", headers


def _consultar(tabla, params):
    """GET paginado: trae todas las filas, de a 1000."""
    base, headers = _config()
    filas, offset = [], 0
    while True:
        r = requests.get(f"{base}/{tabla}", headers=headers, timeout=60,
                         params={**params, "limit": PAGINA, "offset": offset})
        r.raise_for_status()
        lote = r.json()
        filas += lote
        if len(lote) < PAGINA:
            return filas
        offset += PAGINA


def nombre_corto(nombre):
    return re.sub(r"\s*\((en |excluidas|base|billetes).*$", "", nombre).strip()


@st.cache_data(ttl=CACHE, show_spinner=False)
def series():
    if LOCAL:
        df = pd.concat(pd.read_csv(p) for p in (RAIZ / "data" / "processed").glob("*/series.csv"))
    else:
        df = pd.DataFrame(_consultar("series", {"select": "*", "order": "id"}))
    df["nombre_corto"] = df["nombre"].map(nombre_corto)
    return df.set_index("id")


@st.cache_data(show_spinner=False)
def _observaciones_locales():
    return pd.concat(pd.read_csv(p) for p in (RAIZ / "data" / "processed").glob("*/observaciones.csv"))


@st.cache_data(ttl=CACHE, show_spinner=False)
def observaciones(serie_id):
    if LOCAL:
        obs = _observaciones_locales()
        df = obs[obs["serie_id"] == serie_id][["fecha", "valor"]]
    else:
        df = pd.DataFrame(_consultar("observaciones", {
            "select": "fecha,valor", "serie_id": f"eq.{serie_id}", "order": "fecha.asc"}))
    if df.empty:
        return pd.Series(dtype=float, name=serie_id)
    s = pd.Series(df["valor"].astype(float).values, index=pd.to_datetime(df["fecha"]), name=serie_id)
    return s.sort_index()
