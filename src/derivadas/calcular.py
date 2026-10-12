"""Series sintéticas (elaboración propia) calculadas a partir de las series de la base.

Lee los datos de Supabase si hay credenciales (SUPABASE_URL / SUPABASE_SERVICE_KEY),
o de data/processed/ si no las hay. Genera data/processed/derivadas/.

Uso: python src/derivadas/calcular.py
"""
import os
import sys
from pathlib import Path

import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "data" / "processed" / "derivadas"
FUENTE = "Club de Economía UADE (elaboración propia)"
CATEGORIA = "Elaboración propia"

# ---------------------------------------------------------------- lectura
_local = None


def serie(sid):
    """Devuelve la serie como pd.Series indexada por fecha."""
    global _local
    if os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY"):
        sys.path.insert(0, str(RAIZ / "src"))
        from supabase_db import _config
        base, headers = _config()
        filas, offset = [], 0
        while True:
            r = requests.get(f"{base}/observaciones", headers=headers, timeout=60, params={
                "select": "fecha,valor", "serie_id": f"eq.{sid}", "order": "fecha.asc",
                "limit": 1000, "offset": offset})
            r.raise_for_status()
            lote = r.json()
            filas += lote
            if len(lote) < 1000:
                break
            offset += 1000
        df = pd.DataFrame(filas)
    else:
        if _local is None:
            _local = pd.concat(pd.read_csv(p) for p in (RAIZ / "data" / "processed").glob("*/observaciones.csv")
                               if p.parent.name != "derivadas")
        df = _local[_local["serie_id"] == sid]
    if df.empty:
        raise ValueError(f"No hay datos para {sid}")
    return pd.Series(df["valor"].astype(float).values, index=pd.to_datetime(df["fecha"]), name=sid).sort_index()


def mensual(s, como="mean"):
    """Agrega a mensual con la fecha en el primer día del mes (convención de la base)."""
    m = getattr(s.resample("MS"), como)().dropna()
    return m[m.index < pd.Timestamp.today().normalize().replace(day=1)]  # sin el mes en curso (incompleto)


# ---------------------------------------------------------------- cálculos
def calcular():
    reservas, base, tc = serie("bcra_api_74"), serie("bcra_api_71"), serie("bcra_api_84")
    m2, prestamos = serie("bcra_api_109"), serie("bcra_api_117")
    dep_usd, dep_tot, prest_tot = serie("bcra_api_104"), serie("bcra_api_106"), serie("bcra_api_127")
    badlar, itcrm = serie("bcra_api_139"), serie("bcra_itcrm")
    ipc = serie("indec_ipc_nivel_general")
    mes_ipc = ipc.index.max()
    pesos_de = f"{mes_ipc:%m/%Y}"

    out = {}

    # 1. Tipo de cambio "de convertibilidad" y respaldo de la base
    out["club_tc_convertibilidad"] = ((base / reservas).dropna(), dict(
        nombre="Tipo de cambio de convertibilidad (base monetaria / reservas)", unidad="$ por USD", frecuencia="D",
        descripcion="Base monetaria (millones de $) dividida por reservas internacionales brutas (millones de USD). "
                    "Es el tipo de cambio al que las reservas alcanzarían para respaldar toda la base monetaria. "
                    "Fuentes: BCRA (IdVariable 71 y 74)."))
    out["club_respaldo_base"] = ((reservas * tc / base * 100).dropna(), dict(
        nombre="Respaldo de la base monetaria con reservas (al tipo de cambio oficial)", unidad="%", frecuencia="D",
        descripcion="Reservas brutas valuadas al tipo de cambio oficial, como % de la base monetaria. "
                    "Por encima de 100% las reservas cubren toda la base. Usa reservas brutas: no descuenta "
                    "swaps, encajes ni deuda de corto plazo, por lo que sobreestima el respaldo efectivo. "
                    "Fuentes: BCRA (IdVariable 71, 74 y 84)."))

    # 2. Dolarización y profundidad del crédito
    out["club_dolarizacion_depositos"] = ((dep_usd / dep_tot * 100).dropna(), dict(
        nombre="Dolarización de los depósitos privados", unidad="%", frecuencia="D",
        descripcion="Depósitos en dólares del sector privado (expresados en pesos) como % del total de depósitos "
                    "privados en pesos y dólares. Fuentes: BCRA (IdVariable 104 y 106)."))
    out["club_prestamos_depositos"] = ((prest_tot / dep_tot * 100).dropna(), dict(
        nombre="Préstamos sobre depósitos del sector privado", unidad="%", frecuencia="D",
        descripcion="Préstamos totales al sector privado (pesos y dólares) como % de los depósitos privados. "
                    "Mide cuánto de lo que capta el sistema se vuelca a crédito. Fuentes: BCRA (IdVariable 106 y 127)."))

    # 3. Tipo de cambio real vs su promedio histórico
    out["club_itcrm_desvio"] = (((itcrm / itcrm.mean() - 1) * 100).dropna(), dict(
        nombre="Tipo de cambio real multilateral: desvío respecto de su promedio histórico", unidad="%",
        frecuencia="D",
        descripcion=f"ITCRM dividido su promedio desde {itcrm.index.min():%Y}, menos 1. Valores negativos: el peso está "
                    "más apreciado que el promedio (el país está 'caro' en dólares); positivos: más depreciado. "
                    "El promedio se recalcula con cada actualización. Fuente: BCRA (ITCRM)."))

    # 4. Tasa real ex post
    tem = mensual(badlar) / 100 * 30 / 365
    infl = ipc.pct_change()
    real = ((1 + tem) / (1 + infl.shift(-1)) - 1).dropna()
    out["club_tasa_real_badlar"] = ((((1 + real) ** 12 - 1) * 100), dict(
        nombre="Tasa de interés real ex post (BADLAR bancos privados)", unidad="%", frecuencia="M",
        descripcion="Rendimiento real anualizado de un plazo fijo a 30 días constituido en el mes indicado: "
                    "BADLAR promedio del mes (TNA, convertida a tasa efectiva a 30 días) descontada por la inflación "
                    "del mes siguiente. Negativo: el plazo fijo pierde contra la inflación. "
                    "Fuentes: BCRA (IdVariable 139), INDEC (IPC nivel general)."))

    # 5. Carry trade en dólares
    tc_fin = mensual(tc, "last")
    tem_mes = mensual(badlar) / 100 * 30 / 365
    ret = ((1 + tem_mes.shift(1)) * tc_fin.shift(1) / tc_fin - 1).dropna()
    out["club_carry_usd"] = ((1 + ret).cumprod() * 100, dict(
        nombre=f"Carry trade: plazo fijo BADLAR medido en dólares oficiales (base {ret.index.min():%m/%Y}=100)",
        unidad="Índice", frecuencia="M",
        descripcion="Resultado acumulado de pasar dólares a pesos al tipo de cambio oficial, renovar todos los meses "
                    "un plazo fijo a la tasa BADLAR y volver a dólares. Si sube, la tasa le ganó a la devaluación "
                    "(el carry dio ganancia en USD). Para medirlo desde otra fecha, usar la transformación "
                    "'Base 100'. No incluye impuestos ni brecha cambiaria. Fuentes: BCRA (IdVariable 84 y 139)."))

    # 6. Agregados reales (a pesos del último mes con IPC)
    for sid, origen, nombre, idv in [
        ("club_base_real", base, "Base monetaria real", 71),
        ("club_m2_real", m2, "M2 real", 109),
        ("club_prestamos_pesos_real", prestamos, "Préstamos al sector privado en pesos, real", 117),
    ]:
        nominal = mensual(origen)
        real_s = (nominal / ipc * ipc.iloc[-1]).dropna()
        out[sid] = (real_s, dict(
            nombre=f"{nombre} (millones de $ de {pesos_de})", unidad="Millones de $ constantes", frecuencia="M",
            descripcion=f"Promedio mensual del saldo nominal deflactado por el IPC nivel general, expresado en pesos "
                        f"de {pesos_de}. Fuentes: BCRA (IdVariable {idv}), INDEC (IPC). Disponible desde dic-2016, "
                        "inicio del IPC nacional."))
    return out


def main():
    out = calcular()
    metas, obs = [], []
    for sid, (s, m) in out.items():
        s = s.replace([float("inf"), float("-inf")], pd.NA).dropna()
        metas.append({"id": sid, "fuente": FUENTE, "categoria": CATEGORIA, "id_api_bcra": None,
                      "archivo_origen": "src/derivadas/calcular.py", **m})
        obs.append(pd.DataFrame({"serie_id": sid, "fecha": s.index.strftime("%Y-%m-%d"), "valor": s.values}))
        print(f"[ok] {sid}: {len(s):,} datos, último {s.index.max():%Y-%m-%d} = {s.iloc[-1]:,.2f}")
    SALIDA.mkdir(parents=True, exist_ok=True)
    cols = ["id", "nombre", "fuente", "categoria", "unidad", "frecuencia", "id_api_bcra", "archivo_origen", "descripcion"]
    pd.DataFrame(metas)[cols].astype({"id_api_bcra": "Int64"}).to_csv(SALIDA / "series.csv", index=False)
    pd.concat(obs).to_csv(SALIDA / "observaciones.csv", index=False)


if __name__ == "__main__":
    main()
