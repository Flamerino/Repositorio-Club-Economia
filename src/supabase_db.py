"""Conexión mínima a Supabase vía su API REST (PostgREST).

Lee las credenciales de variables de entorno:
    SUPABASE_URL          https://<proyecto>.supabase.co
    SUPABASE_SERVICE_KEY  clave secreta (sb_secret_...) o service_role (solo para escribir; nunca en el frontend)
"""
import json
import math
import os
import time

import requests

LOTE = 5000


def _config():
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise SystemExit("Faltan SUPABASE_URL y/o SUPABASE_SERVICE_KEY en el entorno.")
    headers = {"apikey": key, "Content-Type": "application/json"}
    if key.startswith("eyJ"):  # clave service_role "legacy" (JWT); las nuevas sb_secret_ van solo en apikey
        headers["Authorization"] = f"Bearer {key}"
    url = url.strip().rstrip("/").removesuffix("/rest/v1")  # acepta la URL con o sin /rest/v1
    return url + "/rest/v1", headers


def _limpiar(registros):
    """Convierte NaN a None para que el JSON sea válido."""
    return [{k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in r.items()}
            for r in registros]


def upsert(tabla, registros, clave):
    """Inserta o actualiza en lotes. `clave`: columnas de la clave primaria, ej. 'serie_id,fecha'."""
    base, headers = _config()
    headers = {**headers, "Prefer": "resolution=merge-duplicates,return=minimal"}
    registros = _limpiar(registros)
    for i in range(0, len(registros), LOTE):
        lote = registros[i:i + LOTE]
        for intento in range(3):
            r = requests.post(f"{base}/{tabla}", params={"on_conflict": clave},
                              headers=headers, data=json.dumps(lote), timeout=120)
            if r.ok:
                break
            time.sleep(2 * (intento + 1))
        else:
            raise RuntimeError(f"Error cargando {tabla}: {r.status_code} {r.text[:300]}")
    return len(registros)


def ultima_fecha(serie_id):
    base, headers = _config()
    r = requests.get(f"{base}/observaciones", headers=headers, timeout=60,
                     params={"serie_id": f"eq.{serie_id}", "select": "fecha",
                             "order": "fecha.desc", "limit": 1})
    r.raise_for_status()
    datos = r.json()
    return datos[0]["fecha"] if datos else None


def leer_serie(serie_id):
    """Devuelve [{'fecha','valor'}, ...] de una serie, paginando de a 1000."""
    base, headers = _config()
    filas, offset = [], 0
    while True:
        r = requests.get(f"{base}/observaciones", headers=headers, timeout=60, params={
            "select": "fecha,valor", "serie_id": f"eq.{serie_id}", "order": "fecha.asc",
            "limit": 1000, "offset": offset})
        r.raise_for_status()
        lote = r.json()
        filas += lote
        if len(lote) < 1000:
            return filas
        offset += 1000


def aviso(msg):
    """Muestra el mensaje como advertencia en el resumen de GitHub Actions."""
    print(f"::warning::{msg}")
