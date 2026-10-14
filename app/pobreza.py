"""Pestaña 'Pobreza y precios': precios relativos de la canasta de los hogares pobres
y su efecto sobre la pobreza y la indigencia."""
import numpy as np
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
    s = datos.varias(ids + [i for i in ("indec_pobreza_oficial", "indec_indigencia_oficial") if i in meta.index])

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
    obs_rubros = datos.varias(elegidas)
    for i in elegidas:
        rel[i] = (obs_rubros[i] / gen * 100).dropna()
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
    of_p, of_i = s.get("indec_pobreza_oficial"), s.get("indec_indigencia_oficial")
    if of_p is not None and not of_p.empty and of_p.index[-1] > ult:
        u = of_p.index[-1]
        st.info(f"INDEC ya publicó el {sem(u)}: pobreza {n(of_p[u])}%"
                + (f", indigencia {n(of_i[u])}%" if of_i is not None and u in of_i.index else "") +
                ". La medición del Club (y el contrafactual) se suman cuando INDEC libera los microdatos de la EPH de "
                "los dos trimestres del semestre y las canastas regionales.")
    st.markdown(
        f"Comparamos la pobreza medida con la que habría habido si la canasta hubiera subido igual que la "
        f"inflación general desde 2016, con los mismos ingresos. En el {sem(pico_ef)}, el encarecimiento relativo "
        f"de los alimentos sumó **{n(ef_i[pico_ef])} puntos de indigencia** ({n(ind[pico_ef])}% contra "
        f"{n(ind_cf[pico_ef])}%), unas **{n(personas / 1e6, 1)} millones de personas** en los 31 aglomerados, "
        f"y {n(ef_p[pico_ef])} puntos de pobreza. En el {sem(ult)} el efecto sobre la pobreza es "
        f"{'positivo' if ef_p[ult] > 0 else 'negativo'} ({'+' if ef_p[ult] > 0 else '−'}{n(abs(ef_p[ult]))} p.p.): la canasta " +
        f"{'sigue sumando' if ef_p[ult] > 0 else 'ya sube menos que la inflación y resta'} pobreza.")
    t1, t2 = st.tabs(["Pobreza", "Indigencia"])
    for tab, real, cf, of, nombre in [(t1, pob, pob_cf, of_p, "Pobreza"), (t2, ind, ind_cf, of_i, "Indigencia")]:
        with tab:
            trazas = [linea(real, f"{nombre} medida (Club)", ROJO, "%"),
                      go.Scatter(x=cf.index, y=cf.values, mode="lines", name="Si la canasta siguiera al IPC",
                                 line=dict(color=GRIS, dash="dash"), hovertemplate="%{y:,.1f}%<extra></extra>")]
            if of is not None and not of.empty:
                trazas.append(go.Scatter(x=of.index, y=of.values, mode="markers", name="INDEC (oficial)",
                                         marker=dict(color="#24292f", size=6, symbol="x"),
                                         hovertemplate="%{y:,.1f}%<extra>INDEC</extra>"))
            grafico(trazas, sufijo="%")
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
    render_vulnerabilidad_y_sesgo(meta)


ESTRATOS_GRAF = [  # (id, etiqueta, color) de abajo hacia arriba
    ("club_estrato_indigente", "Indigentes", "#82071e"),
    ("club_estrato_pobre_no_indigente", "Pobres no indigentes", "#cf222e"),
    ("club_estrato_1_11", "Hasta 10% arriba de la línea", "#fb8f44"),
    ("club_estrato_11_125", "10% a 25% arriba", "#f6c343"),
    ("club_estrato_125_15", "25% a 50% arriba", "#fae17d"),
    ("club_estrato_15_2", "1,5 a 2 líneas", "#8ec5ff"),
    ("club_estrato_2_mas", "Más de 2 líneas", "#1f6feb"),
]


def render_vulnerabilidad_y_sesgo(meta):
    ids = [i for i, _, _ in ESTRATOS_GRAF] + ["club_vulnerables", "club_pobreza", "club_pobreza_alineada",
                                               "club_sesgo_inflacion_pobreza", "club_inflacion_canasta_semestral",
                                               "club_poblacion_eph"]
    if any(i not in meta.index for i in ids):
        return
    s = datos.varias(ids)
    st.divider()

    # 3 ---------------------------------------------------------------- vulnerabilidad
    st.subheader("¿Cuánta gente está apenas arriba de la línea?")
    pob, vul, ult = s["club_pobreza"], s["club_vulnerables"], s["club_pobreza"].index[-1]
    cerca10 = s["club_estrato_1_11"][ult]
    personas_vul = vul[ult] / 100 * s["club_poblacion_eph"][ult]
    c1, c2, c3 = st.columns(3)
    c1.metric(f"Pobres · {sem(ult)}", f"{n(pob[ult])}%")
    c2.metric("Vulnerables (hasta 50% arriba)", f"{n(vul[ult])}%")
    c3.metric("Pobres o vulnerables", f"{n(pob[ult] + vul[ult])}%")
    st.markdown(
        f"Además del {n(pob[ult])}% de pobres, otro **{n(vul[ult])}%** de la población (unas {n(personas_vul / 1e6, 1)} "
        f"millones de personas en los 31 aglomerados) tiene ingresos que superan la línea de pobreza por menos de 50%. "
        f"Con ese margen, perder un ingreso o un mes de inflación alta alcanza para caer. En total, **{n(pob[ult] + vul[ult])}% "
        f"de la población es pobre o vulnerable**. La franja vulnerable es muy estable (entre {n(vul.min())}% y "
        f"{n(vul.max())}% desde 2017): cuando la pobreza sube, la franja vulnerable no se achica, sino que toda la "
        f"distribución se corre hacia abajo. Dato de sensibilidad: el {n(cerca10)}% está a menos de 10% de la línea, así que si la canasta "
        f"subiera 10% más que los ingresos, la pobreza pasaría a rondar el {n(pob[ult] + cerca10, 0)}%.")
    fig = go.Figure([go.Bar(x=s[i].index, y=s[i].values, name=nombre, marker_color=color,
                            hovertemplate=f"{nombre}: %{{y:.1f}}%<extra></extra>")
                     for i, nombre, color in ESTRATOS_GRAF])
    fig.update_layout(barmode="stack", height=380, margin=dict(l=0, r=0, t=10, b=0), hovermode="x unified",
                      yaxis=dict(ticksuffix="%", range=[0, 100]), legend=dict(orientation="h", y=-0.12),
                      xaxis=dict(tickformat="%Y"))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    metodologia(meta, "club_vulnerables", "club_estrato_1_11")
    st.divider()

    # 4 ---------------------------------------------------------------- sesgo por inflación
    st.subheader("¿Cuánto puede afectar la inflación a la medición de la pobreza?")
    ali, ses, infl = s["club_pobreza_alineada"], s["club_sesgo_inflacion_pobreza"], s["club_inflacion_canasta_semestral"]
    comun = ses.index.intersection(infl.index)
    pendiente = np.polyfit(infl[comun], ses[comun], 1)[0]
    pico = ses.idxmax()
    texto = (f"La EPH pregunta los ingresos **del mes anterior** a la entrevista, y la medición los compara con la "
             f"canasta del trimestre de la encuesta. Con inflación baja la diferencia es mínima; con inflación alta, "
             f"la canasta puede quedar por delante del ingreso por una cuestión de fechas. Es un **ejercicio de "
             f"sensibilidad**, no una corrección de la cifra oficial: supone que todos los ingresos declarados son del "
             f"mes anterior y trabaja con promedios trimestrales, porque la base pública no trae el mes de la "
             f"entrevista. Con ese supuesto, alinear ingreso y canasta al mismo mes llevaría la pobreza del "
             f"{sem(pico)} de {n(pob[pico])}% a {n(ali[pico])}% ({n(ses[pico])} puntos de diferencia), y en la "
             f"serie cada punto de inflación mensual se asocia con unos {n(pendiente, 2)} puntos de diferencia.")
    a, b = pd.Timestamp("2024-01-01"), pd.Timestamp("2024-07-01")
    if a in pob.index and b in pob.index:
        texto += (f" Bajo el mismo supuesto, de la baja de {n(pob[a] - pob[b])} puntos entre el 1° y el 2° semestre "
                  f"de 2024 ({n(pob[a])}% → {n(pob[b])}%), la serie alineada muestra {n(ali[a] - ali[b])}: la "
                  "diferencia sería el efecto del desfase al bajar la inflación.")
    st.markdown(texto)
    g1, g2 = st.columns([3, 2])
    with g1:
        grafico([linea(pob, "Pobreza medida", ROJO, "%"),
                 go.Scatter(x=ali.index, y=ali.values, mode="lines", name="Ingreso y canasta del mismo mes",
                            line=dict(color=AZUL, dash="dash"), hovertemplate="%{y:,.1f}%<extra></extra>")],
                sufijo="%")
    with g2:
        fig = go.Figure(go.Scatter(x=infl[comun], y=ses[comun], mode="markers+text", text=[sem(f) for f in comun],
                                   textposition="top center", textfont=dict(size=9), marker=dict(color=ROJO, size=8),
                                   hovertemplate="Inflación %{x:.1f}% → sesgo %{y:.1f} p.p.<extra></extra>"))
        xs = np.linspace(0, infl[comun].max(), 20)
        fig.add_trace(go.Scatter(x=xs, y=np.polyval(np.polyfit(infl[comun], ses[comun], 1), xs), mode="lines",
                                 line=dict(color=GRIS, dash="dot"), hoverinfo="skip"))
        fig.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0), showlegend=False,
                          xaxis_title="Inflación mensual de la canasta (%)", yaxis_title="Sobreestimación (p.p.)")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    metodologia(meta, "club_pobreza_alineada", "club_sesgo_inflacion_pobreza")
