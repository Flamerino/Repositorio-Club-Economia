"""Pestaña 'Análisis': series de elaboración propia con lectura de la coyuntura.

Los textos con números se calculan con el último dato disponible, así no quedan desactualizados.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import datos

VERDE, ROJO, AZUL, GRIS = "#1a7f37", "#cf222e", "#1f6feb", "#8c959f"


def n(v, dec=1):
    """Número con formato argentino."""
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def grafico(trazas, ref=None, alto=340, sufijo=""):
    fig = go.Figure(trazas)
    if ref is not None:
        fig.add_hline(y=ref, line_dash="dot", line_color=GRIS)
    fig.update_layout(height=alto, margin=dict(l=0, r=0, t=10, b=0), hovermode="x unified",
                      legend=dict(orientation="h", y=1.08), yaxis=dict(ticksuffix=sufijo))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def linea(s, nombre, color=AZUL, sufijo=""):
    return go.Scatter(x=s.index, y=s.values, mode="lines", name=nombre, line=dict(color=color, width=1.8),
                      hovertemplate=f"%{{y:,.1f}}{sufijo}<extra>{nombre}</extra>")


def barras(s, nombre, sufijo="%"):
    return go.Bar(x=s.index, y=s.values, name=nombre, marker_color=[VERDE if v >= 0 else ROJO for v in s.values],
                  hovertemplate=f"%{{x|%m/%Y}}: %{{y:,.1f}}{sufijo}<extra></extra>")


def metodologia(meta, *ids):
    with st.expander("Cómo se calcula"):
        for sid in ids:
            if sid in meta.index:
                st.markdown(f"**{meta.loc[sid, 'nombre']}**  \n{meta.loc[sid].get('descripcion') or ''}")


def render(meta):
    ids = ["club_respaldo_base", "club_tc_convertibilidad", "club_tasa_real_badlar", "club_carry_usd",
           "club_itcrm_desvio", "club_dolarizacion_depositos", "club_base_real", "club_m2_real",
           "club_prestamos_pesos_real", "bcra_api_84"]
    faltan = [i for i in ids if i not in meta.index]
    if faltan:
        st.info("Las series de elaboración propia todavía no están cargadas en la base.")
        return
    s = {i: datos.observaciones(i) for i in ids}

    st.markdown("Series construidas por el Club cruzando datos oficiales. Cada una responde una pregunta; "
                "los números se recalculan solos con cada actualización.")

    # 1 ---------------------------------------------------------------- respaldo
    st.subheader("¿Alcanzan las reservas para respaldar los pesos?")
    resp, conv, tc = s["club_respaldo_base"], s["club_tc_convertibilidad"], s["bcra_api_84"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Respaldo de la base", f"{n(resp.iloc[-1], 0)}%")
    c2.metric("Tipo de cambio de convertibilidad", f"$ {n(conv.iloc[-1], 0)}")
    c3.metric("Tipo de cambio oficial", f"$ {n(tc.iloc[-1], 0)}")
    estado = "alcanzarían para cubrir" if resp.iloc[-1] >= 100 else "no alcanzarían para cubrir"
    st.markdown(f"Al tipo de cambio oficial, las reservas brutas {estado} toda la base monetaria "
                f"({n(resp.iloc[-1], 0)}%). El mínimo de la serie fue {n(resp.min(), 0)}% en "
                f"{resp.idxmin():%m/%Y} y el máximo, {n(resp.max(), 0)}% en {resp.idxmax():%m/%Y}.")
    grafico([linea(resp, "Respaldo", sufijo="%")], ref=100, sufijo="%")
    metodologia(meta, "club_respaldo_base", "club_tc_convertibilidad")
    st.divider()

    # 2 ---------------------------------------------------------------- tasa real
    st.subheader("¿Le gana el plazo fijo a la inflación?")
    tr = s["club_tasa_real_badlar"]
    ult12 = tr.tail(12)
    st.markdown(f"Con datos hasta {tr.index[-1]:%m/%Y}, la tasa real ex post de la BADLAR fue "
                f"**{n(tr.iloc[-1])}% anual**. En los últimos 12 meses fue positiva en "
                f"{(ult12 > 0).sum()} de 12. Desde 2017 lo fue en {n((tr > 0).mean() * 100, 0)}% de los meses.")
    grafico([barras(tr, "Tasa real")], ref=0, sufijo="%")
    metodologia(meta, "club_tasa_real_badlar")
    st.divider()

    # 3 ---------------------------------------------------------------- carry
    st.subheader("¿Cuánto rindió en dólares hacer plazo fijo en pesos?")
    carry = s["club_carry_usd"]
    r12 = (carry / carry.shift(12) - 1).dropna() * 100
    mejor, peor = r12.idxmax(), r12.idxmin()
    st.markdown(f"Un plazo fijo renovado durante los 12 meses a {carry.index[-1]:%m/%Y} rindió "
                f"**{n(r12.iloc[-1])}% en dólares oficiales**. El mejor año móvil de la serie terminó en "
                f"{mejor:%m/%Y} ({n(r12[mejor], 0)}%) y el peor en {peor:%m/%Y} ({n(r12[peor], 0)}%).")
    grafico([barras(r12, "Rendimiento en USD, 12 meses")], ref=0, sufijo="%")
    metodologia(meta, "club_carry_usd")
    st.divider()

    # 4 ---------------------------------------------------------------- ITCRM
    st.subheader("¿Está Argentina cara o barata en dólares?")
    it = s["club_itcrm_desvio"]
    lado = "más apreciado" if it.iloc[-1] < 0 else "más depreciado"
    pct_mas_caro = (it < it.iloc[-1]).mean() * 100
    st.markdown(f"El tipo de cambio real multilateral está **{n(abs(it.iloc[-1]))}% {lado}** que su promedio "
                f"desde {it.index.min():%Y}. En el {n(pct_mas_caro, 0)}% de los días desde entonces el "
                "peso estuvo más apreciado que hoy.")
    grafico([linea(it, "Desvío vs promedio", sufijo="%")], ref=0, sufijo="%")
    metodologia(meta, "club_itcrm_desvio")
    st.divider()

    # 5 ---------------------------------------------------------------- dolarización
    st.subheader("¿Se dolarizan los ahorros?")
    dol = s["club_dolarizacion_depositos"]
    hace_un_anio = dol[: dol.index[-1] - pd.DateOffset(years=1)].iloc[-1]
    st.markdown(f"El **{n(dol.iloc[-1])}%** de los depósitos privados está en dólares, "
                f"{'más' if dol.iloc[-1] > hace_un_anio else 'menos'} que hace un año ({n(hace_un_anio)}%).")
    grafico([linea(dol, "Dolarización", sufijo="%")], sufijo="%")
    metodologia(meta, "club_dolarizacion_depositos")
    st.divider()

    # 6 ---------------------------------------------------------------- agregados reales
    st.subheader("¿Cuánto dinero y crédito hay en términos reales?")
    reales = {"Base monetaria": s["club_base_real"], "M2": s["club_m2_real"],
              "Préstamos en pesos": s["club_prestamos_pesos_real"]}
    indices = {k: v / v.iloc[0] * 100 for k, v in reales.items()}
    pr = reales["Préstamos en pesos"]
    var12 = (pr.iloc[-1] / pr.iloc[-13] - 1) * 100 if len(pr) > 12 else float("nan")
    st.markdown(f"Descontada la inflación, los préstamos en pesos al sector privado "
                f"{'crecieron' if var12 >= 0 else 'cayeron'} **{n(abs(var12))}%** en los últimos 12 meses "
                f"(a {pr.index[-1]:%m/%Y}). Gráfico en índice dic-2016 = 100.")
    grafico([linea(v, k, color=c) for (k, v), c in zip(indices.items(), [AZUL, "#8250df", "#bf8700"])], ref=100)
    metodologia(meta, "club_base_real", "club_m2_real", "club_prestamos_pesos_real")
