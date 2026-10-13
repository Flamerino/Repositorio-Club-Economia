"""Pestaña 'Pobreza y precios': precios relativos de la canasta de los hogares pobres
y su efecto sobre la pobreza y la indigencia."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import datos
from analisis import AZUL, GRIS, ROJO, VERDE, grafico, linea, metodologia, n

NARANJA, VIOLETA = "#bf8700", "#8250df"
NO_DIVISIONES = {"nivel_general", "nucleo", "regulados", "estacional", "bienes", "servicios"}


def sem(fecha):
    return f"{'1°' if fecha.month <= 6 else '2°'} sem. {fecha.year}"


def render(meta):
    ids = ["club_cba_real", "club_cbt_real", "club_pobreza", "club_indigencia", "club_pobreza_contrafactual",
           "club_indigencia_contrafactual", "club_efecto_canasta_pobreza", "club_efecto_canasta_indigencia",
           "club_poblacion_eph", "indec_ipc_nivel_general"]
    if any(i not in meta.index for i in ids):
        st.info("Las series de pobreza todavía no están cargadas en la base.")
        return
    s = {i: datos.observaciones(i) for i in ids}

    st.markdown("¿Subió más de lo normal lo que consumen los hogares de menores ingresos? ¿Cuánta pobreza "
                "explica eso? Usamos las canastas básicas de INDEC, que son la canasta de referencia de esos "
                "hogares y las líneas oficiales de pobreza (CBT) e indigencia (CBA), y la EPH para medir la pobreza.")

    # 1 ---------------------------------------------------------------- canastas reales
    st.subheader("¿Se encareció la canasta de los hogares pobres?")
    cba, cbt = s["club_cba_real"], s["club_cbt_real"]
    pico = cba.idxmax()
    st.markdown(f"Descontada la inflación general, la **canasta alimentaria (CBA)** de GBA está en "
                f"**{n(cba.iloc[-1])}** ({cba.index[-1]:%m/%Y}, dic-2016 = 100): "
                f"{'más cara' if cba.iloc[-1] > 100 else 'más barata'} que el promedio de precios. Su pico fue "
                f"{n(cba[pico])} en {pico:%m/%Y}: los alimentos, el rubro de mayor peso en el gasto de los "
                f"hogares pobres, subieron mucho más que el resto. La **canasta total (CBT)**, que suma bienes y "
                f"servicios no alimentarios, está en {n(cbt.iloc[-1])}.")
    grafico([linea(cba, "Canasta alimentaria (CBA)", ROJO), linea(cbt, "Canasta total (CBT)", NARANJA)], ref=100)
    metodologia(meta, "club_cba_real", "club_cbt_real")

    st.markdown("**Por rubros del IPC.** Precio de cada rubro dividido el nivel general (dic-2016 = 100). "
                "Arriba de 100: el rubro se encareció en términos reales.")
    divisiones = [i for i in meta.index if i.startswith("indec_ipc_")
                  and i.removeprefix("indec_ipc_") not in NO_DIVISIONES]
    etiqueta = lambda i: meta.loc[i, "nombre"].removeprefix("IPC ").split(" (")[0]  # noqa: E731
    defecto = [i for i in ["indec_ipc_alimentos_y_bebidas_no_alcoholicas",
                           "indec_ipc_vivienda_agua_electricidad_gas_y_otros_combustibles",
                           "indec_ipc_transporte", "indec_ipc_salud"] if i in divisiones]
    elegidas = st.multiselect("Rubros", divisiones, default=defecto, format_func=etiqueta, key="rubros_pobreza")
    gen = s["indec_ipc_nivel_general"]
    colores = [ROJO, AZUL, NARANJA, VIOLETA, VERDE, GRIS]
    rel = {}
    for i, c in zip(elegidas, colores * 3):
        rel[i] = (datos.observaciones(i) / gen * 100).dropna()
    if rel:
        grafico([linea(v, etiqueta(i), c) for (i, v), c in zip(rel.items(), colores * 3)], ref=100)
        ult = {etiqueta(i): v.iloc[-1] for i, v in rel.items()}
        arriba = [f"{k} ({n(v)})" for k, v in sorted(ult.items(), key=lambda x: -x[1]) if v > 100]
        abajo = [f"{k} ({n(v)})" for k, v in sorted(ult.items(), key=lambda x: x[1]) if v <= 100]
        st.caption(f"A {gen.index[-1]:%m/%Y}. Más caros que en 2016 en términos reales: "
                   f"{', '.join(arriba) or 'ninguno'}. Más baratos: {', '.join(abajo) or 'ninguno'}.")
    st.divider()

    # 2 ---------------------------------------------------------------- pobreza
    st.subheader("¿Cuánto pesó en la pobreza?")
    pob, pob_cf = s["club_pobreza"], s["club_pobreza_contrafactual"]
    ind, ind_cf = s["club_indigencia"], s["club_indigencia_contrafactual"]
    ef_p, ef_i, poblacion = s["club_efecto_canasta_pobreza"], s["club_efecto_canasta_indigencia"], s["club_poblacion_eph"]
    ult = pob.index[-1]
    pico_ef = ef_i.idxmax()
    personas = ef_i[pico_ef] / 100 * poblacion[pico_ef]
    c1, c2, c3 = st.columns(3)
    c1.metric(f"Pobreza · {sem(ult)}", f"{n(pob[ult])}%")
    c2.metric(f"Indigencia · {sem(ult)}", f"{n(ind[ult])}%")
    c3.metric("Efecto de la canasta en la pobreza", f"{'+' if ef_p[ult] > 0 else '−'}{n(abs(ef_p[ult]))} p.p.")
    st.markdown(
        f"Comparamos la pobreza medida con la que habría habido si la canasta hubiera subido igual que la "
        f"inflación general desde 2016, con los mismos ingresos. En el {sem(pico_ef)}, el encarecimiento relativo "
        f"de los alimentos sumó **{n(ef_i[pico_ef])} puntos de indigencia** ({n(ind[pico_ef])}% contra "
        f"{n(ind_cf[pico_ef])}%), unas **{n(personas / 1e6, 1)} millones de personas** en los 31 aglomerados, "
        f"y {n(ef_p[pico_ef])} puntos de pobreza. En el {sem(ult)} el efecto sobre la pobreza es "
        f"{'positivo' if ef_p[ult] > 0 else 'negativo'} ({'+' if ef_p[ult] > 0 else '−'}{n(abs(ef_p[ult]))} p.p.): la canasta " +
        f"{'sigue sumando' if ef_p[ult] > 0 else 'ya sube menos que la inflación y resta'} pobreza.")
    t1, t2 = st.tabs(["Pobreza", "Indigencia"])
    for tab, real, cf, nombre in [(t1, pob, pob_cf, "Pobreza"), (t2, ind, ind_cf, "Indigencia")]:
        with tab:
            grafico([linea(real, f"{nombre} medida", ROJO, "%"),
                     go.Scatter(x=cf.index, y=cf.values, mode="lines", name="Si la canasta siguiera al IPC",
                                line=dict(color=GRIS, dash="dash"), hovertemplate="%{y:,.1f}%<extra></extra>")],
                    sufijo="%")
    st.markdown("**Efecto de la canasta, en puntos porcentuales**")
    fig = go.Figure([go.Bar(x=ef_p.index, y=ef_p.values, name="Pobreza", marker_color=ROJO,
                            hovertemplate="%{y:+.1f} p.p.<extra>Pobreza</extra>"),
                     go.Bar(x=ef_i.index, y=ef_i.values, name="Indigencia", marker_color=NARANJA,
                            hovertemplate="%{y:+.1f} p.p.<extra>Indigencia</extra>")])
    fig.update_layout(barmode="group", height=300, margin=dict(l=0, r=0, t=10, b=0),
                      legend=dict(orientation="h", y=1.1), hovermode="x unified")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    metodologia(meta, "club_pobreza", "club_pobreza_contrafactual", "club_efecto_canasta_pobreza")
    st.caption("Limitaciones: el contrafactual mantiene fijos los ingresos (no modela cómo habrían cambiado salarios "
               "o jubilaciones con otros precios), usa el IPC nacional para todas las regiones y acumula desde "
               "dic-2016, así que el resultado depende de ese punto de partida. Cubre los 31 aglomerados de la EPH.")
