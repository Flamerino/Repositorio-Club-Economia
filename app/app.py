"""Datos económicos — Club de Economía UADE."""
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analisis  # noqa: E402
import datos  # noqa: E402

st.set_page_config(page_title="Datos económicos · Club de Economía UADE", page_icon="📈", layout="wide")

RESUMEN = [  # (serie, título, cómo mostrar el cambio)
    ("bcra_api_74", "Reservas internacionales", "abs"),
    ("bcra_api_84", "Tipo de cambio oficial", "pct"),
    ("bcra_api_71", "Base monetaria", "pct"),
    ("bcra_api_197", "M2 transaccional privado", "pct"),
    ("bcra_api_139", "Tasa BADLAR bancos privados (TNA)", "pp"),
    ("bcra_itcrm", "Tipo de cambio real multilateral", "pct"),
]
FRECUENCIAS = {"Original": None, "Promedio mensual": "mean", "Fin de mes": "last"}
TRANSFORMACIONES = ["Nivel", "Variación % mensual", "Variación % interanual", "Base 100 (inicio del período)"]


def formato(v, unidad):
    if pd.isna(v):
        return "—"
    if unidad == "%":
        return f"{v:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")
    txt = f"{v:,.0f}" if abs(v) >= 1000 else f"{v:,.2f}"
    return txt.replace(",", "X").replace(".", ",").replace("X", ".")


def escalar(v, unidad):
    """Montos en millones de $ muy grandes se muestran en billones (10^12)."""
    if unidad == "Millones de $" and abs(v) >= 1e6:
        return v / 1e6, "Billones de $"
    return v, unidad


def a_mensual(s, como):
    return getattr(s.resample("ME"), como)().dropna()


def transformar(s, frecuencia, transf):
    if transf in ("Variación % mensual", "Variación % interanual") and frecuencia == "Original":
        frecuencia = "Fin de mes"  # las variaciones se calculan sobre datos mensuales
    if FRECUENCIAS[frecuencia]:
        s = a_mensual(s, FRECUENCIAS[frecuencia])
    if transf == "Variación % mensual":
        s = s.pct_change(1, fill_method=None) * 100
    elif transf == "Variación % interanual":
        s = s.pct_change(12, fill_method=None) * 100
    elif transf.startswith("Base 100") and not s.empty and s.iloc[0] != 0:
        s = s / s.iloc[0] * 100
    return s.dropna(), frecuencia


# ---------------------------------------------------------------- carga
try:
    meta = datos.series()
except Exception as e:  # noqa: BLE001
    st.error(f"No se pudo conectar con la base de datos: {e}")
    st.stop()

st.title("📈 Datos económicos de Argentina")
c_tit, c_btn = st.columns([5, 1])
c_tit.caption("Club de Economía UADE · Series oficiales actualizadas automáticamente todas las semanas")
if c_btn.button("🔄 Refrescar datos", help="Vuelve a leer la base (por defecto se guarda 6 horas)"):
    st.cache_data.clear()
    st.rerun()

tab_resumen, tab_analisis, tab_explorar, tab_datos = st.tabs(["Resumen", "Análisis", "Explorar series", "Sobre los datos"])

# ---------------------------------------------------------------- resumen
with tab_resumen:
    cols = st.columns(3)
    for i, (sid, titulo, tipo_delta) in enumerate([r for r in RESUMEN if r[0] in meta.index]):
        m = meta.loc[sid]
        s = datos.observaciones(sid)
        with cols[i % 3], st.container(border=True):
            if s.empty:
                st.metric(titulo, "Sin datos")
                continue
            ult, fecha = s.iloc[-1], s.index[-1]
            previo = s[: fecha - pd.DateOffset(days=30)]
            delta = None
            if not previo.empty:
                p = previo.iloc[-1]
                if tipo_delta == "pct" and p:
                    delta = f"{(ult / p - 1) * 100:+.1f}% en 30 días"
                elif tipo_delta == "pp":
                    delta = f"{ult - p:+.2f} p.p. en 30 días"
                else:
                    delta = f"{'+' if ult >= p else ''}{formato(ult - p, m['unidad'])} en 30 días"
            valor, unidad = escalar(ult, m["unidad"])
            st.metric(titulo, formato(valor, unidad) if unidad != "Billones de $" else f"{valor:,.1f}".replace(".", ","),
                      delta, help=m["nombre"])
            st.caption(f"{unidad or ''} · al {fecha:%d/%m/%Y}")
            ult2 = s[s.index >= fecha - pd.DateOffset(years=2)]
            fig = go.Figure(go.Scatter(x=ult2.index, y=ult2.values, mode="lines",
                                       line=dict(width=2), hovertemplate="%{x|%d/%m/%Y}: %{y:,.2f}<extra></extra>"))
            fig.update_layout(height=140, margin=dict(l=0, r=0, t=4, b=0), showlegend=False,
                              xaxis=dict(visible=False), yaxis=dict(visible=False))
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=f"spark_{sid}")
    st.caption("Últimos 2 años. Para ver la historia completa, comparar series o descargar datos, usá *Explorar series*.")

# ---------------------------------------------------------------- análisis
with tab_analisis:
    analisis.render(meta)

# ---------------------------------------------------------------- explorar
with tab_explorar:
    c1, c2 = st.columns([1, 2])
    with c1:
        categorias = sorted(meta["categoria"].dropna().unique())
        cat = st.multiselect("Categoría", categorias, default=["Reservas"])
    opciones = meta[meta["categoria"].isin(cat)] if cat else meta
    with c2:
        sel = st.multiselect("Series (hasta 6)", opciones.index.tolist(), max_selections=6,
                             default=[x for x in ["bcra_api_74"] if x in opciones.index],
                             format_func=lambda x: f"{meta.loc[x, 'nombre_corto']} · {meta.loc[x, 'unidad'] or ''}")

    c3, c4, c5 = st.columns(3)
    frecuencia = c3.selectbox("Frecuencia", list(FRECUENCIAS))
    transf = c4.selectbox("Transformación", TRANSFORMACIONES)
    desde_hasta = c5.date_input("Período", (date(2015, 1, 1), date.today()), format="DD/MM/YYYY")

    if not sel:
        st.info("Elegí una o más series para graficar.")
    else:
        d0, d1 = (desde_hasta + (date.today(),))[:2] if len(desde_hasta) else (date(2003, 1, 1), date.today())
        procesadas, freq_usada = {}, frecuencia
        for sid in sel:
            s = datos.observaciones(sid)
            s = s[(s.index >= pd.Timestamp(d0)) & (s.index <= pd.Timestamp(d1))]
            procesadas[sid], freq_usada = transformar(s, frecuencia, transf)
        if freq_usada != frecuencia:
            st.caption("Las variaciones se calculan sobre el dato de fin de mes.")

        unidades = {meta.loc[x, "unidad"] if transf == "Nivel" else transf for x in sel}
        separar = st.toggle("Un gráfico por serie", value=len(unidades) > 1,
                            help="Útil cuando las series tienen unidades distintas")
        filas = len(sel) if separar else 1
        fig = make_subplots(rows=filas, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                            subplot_titles=[meta.loc[x, "nombre_corto"] for x in sel] if separar else None)
        for i, sid in enumerate(sel):
            s = procesadas[sid]
            fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines", name=meta.loc[sid, "nombre_corto"],
                                     hovertemplate="%{x|%d/%m/%Y}: %{y:,.2f}<extra></extra>"),
                          row=i + 1 if separar else 1, col=1)
        fig.update_layout(height=max(420, 260 * filas) if separar else 480, hovermode="x unified",
                          legend=dict(orientation="h", y=-0.15), margin=dict(l=0, r=0, t=30, b=0))
        if not separar and len(unidades) == 1:
            fig.update_yaxes(title_text=next(iter(unidades)))
        st.plotly_chart(fig, width="stretch")

        tabla = pd.DataFrame({meta.loc[x, "nombre_corto"]: procesadas[x] for x in sel})
        tabla.index.name = "fecha"
        with st.expander(f"Ver tabla ({len(tabla):,} filas)".replace(",", ".")):
            st.dataframe(tabla.sort_index(ascending=False), width="stretch")
        st.download_button("⬇️ Descargar CSV", tabla.to_csv().encode("utf-8-sig"),
                           file_name="series_club_economia.csv", mime="text/csv")

        with st.expander("Ficha de las series"):
            for sid in sel:
                m, s = meta.loc[sid], datos.observaciones(sid)
                st.markdown(f"**{m['nombre']}**")
                api = f" · IdVariable API BCRA: {int(m['id_api_bcra'])}" if pd.notna(m.get("id_api_bcra")) else ""
                rango = f"{s.index.min():%d/%m/%Y} – {s.index.max():%d/%m/%Y}" if not s.empty else "sin datos"
                st.caption(f"`{sid}` · Fuente: {m['fuente']} · Unidad: {m['unidad'] or '—'} · "
                           f"Frecuencia: {m['frecuencia']} · Datos: {rango}{api}")
                if isinstance(m.get("descripcion"), str) and m["descripcion"]:
                    st.caption(m["descripcion"])

# ---------------------------------------------------------------- sobre los datos
with tab_datos:
    st.markdown(
        "Las series se descargan de fuentes oficiales, se limpian y se cargan en una base de datos que se "
        "actualiza automáticamente todos los lunes. El código está en "
        "[GitHub](https://github.com/Flamerino/Repositorio-Club-Economia).")
    resumen = meta.groupby(["fuente", "categoria"]).size().rename("series").reset_index()
    st.dataframe(resumen, hide_index=True, width="stretch")
    st.markdown("**Catálogo completo**")
    st.dataframe(meta[["nombre", "fuente", "categoria", "unidad", "frecuencia"]],
                 width="stretch", height=400)
