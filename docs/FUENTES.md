# Fuentes

Para cada fuente: qué aporta, de dónde se obtiene, cada cuánto se actualiza y qué control pasa antes de guardarse. Si una fuente no responde o no pasa el control, se conservan sus datos anteriores y la corrida del workflow deja un aviso.

La columna **Página** indica si la fuente se muestra en la [página web](https://club-economia-uade.streamlit.app/) o está solo en el repositorio.

## Fuentes oficiales argentinas

| Fuente | Series | Obtención | Control | Página | Código |
|---|---|---|---|---|---|
| **BCRA**: principales variables | 154 series diarias desde 2003: reservas, base monetaria, depósitos, préstamos, tasas, instrumentos | Historia: `SerieReservas.xlsm`. Actualización: API Estadísticas Monetarias v4.0 | La hoja `API_Series` del propio BCRA vincula cada columna con su `IdVariable` | Sí | `src/bcra/limpiar.py`, `src/bcra/actualizar_api.py` |
| **BCRA**: tipo de cambio real | ITCRM y 14 bilaterales, diarios desde 1997 | `ITCRMSerie.xlsx` del sitio del BCRA | Historia anterior a 6 meses: diferencia mediana < 1% | Sí | `src/bcra/actualizar_itcrm.py` |
| **BCRA**: balance cambiario | 182 series mensuales desde 2003: balance cambiario, cuenta financiera por sector, mercado de cambios, tarjetas y viajes | Anexo estadístico del balance cambiario | Archivo nuevo: historia contra el anterior, diferencia mediana < 1% | No | `src/bcra/balance_cambiario.py` |
| **BCRA**: REM | Expectativas de inflación (12 meses, mes en curso, año en curso), dólar a 12 meses, crecimiento | Libro histórico del Relevamiento de Expectativas de Mercado | Al menos 60 encuestas, valores en rango posible | No | `src/bcra/rem.py` |
| **INDEC**: IPC | Nivel general y 17 aperturas, mensual desde dic-2016 | Archivo del IPC; nivel general actualizado por API de datos.gob.ar | Meses en común idénticos (tolerancia 0,1%) | Sí | `src/indec/limpiar.py`, `src/indec/actualizar_ipc.py` |
| **INDEC**: EPH y canastas | Microdatos 2017 en adelante; CBA y CBT por región | Espejo de [pyeph](https://github.com/reflejar/pyeph-data), completado con descargas directas del INDEC | Ver [metodología](METODOLOGIA.md) | Sí | `src/indec/pobreza.py` |
| **INDEC, Trabajo, ANSES, Hacienda, Energía, Agricultura** (vía datos.gob.ar) | EMAE, PIB, IPI, ISAC, comercio exterior, balanza de pagos, términos del intercambio, salarios, RIPTE, salario mínimo, haber mínimo, AUH, desocupación, informalidad, empleo registrado, resultado fiscal, ingresos, gasto, intereses, aperturas del IPC, canastas, producción de petróleo y gas, cosechas | API de Series de Tiempo ([apis.datos.gob.ar](https://apis.datos.gob.ar/series)) | Ver abajo | No | `src/datos_gob/` |

**Controles de datos.gob.ar.** Cada serie del [catálogo](../src/datos_gob/catalogo.py) declara las palabras que deben aparecer en la descripción que devuelve la API. Si el ID no coincide, la serie se busca por texto y solo se acepta si hay un único candidato. Además, una serie no puede cambiar su historia más de 5% respecto de lo guardado, y se avisa si su último dato es demasiado viejo. El índice de salarios se toma del CSV del INDEC, porque la API llegó a estar meses sin actualizarse. El reporte de cada corrida está en [`data/raw/datos_gob/ESTADO.csv`](../data/raw/datos_gob/ESTADO.csv).

## Encuestas y opinión pública

| Fuente | Series | Obtención | Control | Código |
|---|---|---|---|---|
| **Universidad Torcuato Di Tella**: Índice de Confianza en el Gobierno | ICG mensual desde nov-2001, sus 5 componentes y el índice por zona, sexo, edad y nivel educativo | Microdatos que mantiene el paquete [opinAr](https://github.com/PoliticaArgentina/opinAr) | Escala 0 a 5; la historia no puede cambiar más de 0,05 puntos | `src/opinion/actualizar.py` |

## Fuentes no oficiales

| Fuente | Series | Control | Código |
|---|---|---|---|
| **[ArgentinaDatos](https://argentinadatos.com)** | Dólar oficial minorista, mayorista, blue, MEP y CCL; brechas; riesgo país (diarios) | Su mayorista debe coincidir con el A3500 del BCRA (diferencia mediana histórica 0,08%) | `src/mercados/actualizar.py` |

Advertencias: el **dólar blue** viene redondeado a pesos enteros, así que antes de 2020 el redondeo pesa entre 5% y 25% del precio y la serie queda igual durante meses. Por eso la brecha del blue empieza en agosto de 2019. Se eliminan los fines de semana y feriados, que la fuente rellena repitiendo el último dato.

## Contexto internacional

| Fuente | Series | Control | Código |
|---|---|---|---|
| **Banco Mundial** (World Development Indicators) | 8 indicadores × 11 países (Argentina, región, América Latina y el Caribe, mundo): crecimiento, inflación, PIB per cápita PPA, desempleo, Gini, inversión, exportaciones, deuda | Crecimiento de Argentina contra el archivo del Banco Mundial guardado en `data/raw/` | `src/banco_mundial/actualizar.py` |
| **FMI** (World Economic Outlook) | 7 indicadores × 9 países, incluidas las proyecciones del FMI | Crecimiento de Argentina contra el Banco Mundial (diferencia mediana < 1 punto) | `src/internacional/actualizar.py` |
| **FRED** (Reserva Federal de St. Louis) | Tasa de la Fed, bono a 10 años, dólar global; precios de soja, harina y aceite de soja, maíz, trigo y petróleo | Rango plausible de cada serie | `src/internacional/actualizar.py` |
| **Banco Central de Brasil** | Actividad (IBC-Br), inflación, tasa Selic, tipo de cambio | Rango plausible de cada serie | `src/internacional/actualizar.py` |
| **Proyecto Maddison** (Universidad de Groningen) | PIB per cápita histórico de Argentina y 9 países de comparación | Huella SHA-256 del archivo oficial `mpd2023_web.xlsx` | `src/internacional/actualizar.py` |

## Archivos originales sin procesar

`data/raw/` conserva archivos originales que todavía no se convierten en series: deuda pública (Ministerio de Economía), recaudación (Oficina de Presupuesto del Congreso), balances del BCRA, información monetaria diaria y la base de series del BCRA (`es_series.txt` y `tasa_ser.zip`).
