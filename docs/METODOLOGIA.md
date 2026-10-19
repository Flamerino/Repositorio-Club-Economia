# Metodología

Cómo se construyen las series de elaboración propia y qué convenciones siguen todas las series del repositorio.

## Convenciones generales

- **Fechas.** Los datos mensuales se fechan el primer día del mes; los trimestrales, el primer día del trimestre (`2025-04-01` = 2° trimestre); los semestrales, el 1 de enero o el 1 de julio; los anuales, el 1 de enero.
- **Períodos incompletos.** Las series mensuales calculadas a partir de datos diarios no incluyen el mes en curso.
- **Días hábiles.** Las cotizaciones diarias se publican solo para días con mercado.
- **Unidades.** Cada serie declara su unidad en el índice. Los montos en "millones de $" están en pesos corrientes, salvo que digan "constantes".

## Pobreza e indigencia

`src/indec/pobreza.py` replica la metodología oficial del INDEC con los microdatos de la EPH (31 aglomerados urbanos):

1. **Línea por hogar.** Se suman los adultos equivalentes del hogar (según edad y sexo de cada miembro) y se multiplican por la Canasta Básica Total (pobreza) o Alimentaria (indigencia) de su región, promedio del trimestre.
2. **Clasificación.** Un hogar es pobre si su ingreso total familiar (ITF) es menor que su línea.
3. **Tasa.** Porcentaje de personas en hogares pobres, con el ponderador de ingresos `PONDIH` (excluye hogares que no informaron ingresos), por semestre.

**Validación contra el INDEC** (% de personas bajo la línea de pobreza):

| Semestre | Club | INDEC | | Semestre | Club | INDEC |
|---|---|---|---|---|---|---|
| 1° 2017 | 28,5 | 28,6 | | 1° 2022 | 36,3 | 36,5 |
| 2° 2017 | 25,6 | 25,7 | | 2° 2022 | 39,4 | 39,2 |
| 1° 2018 | 27,3 | 27,3 | | 1° 2023 | 40,0 | 40,1 |
| 2° 2018 | 31,8 | 32,0 | | 2° 2023 | 41,9 | 41,7 |
| 1° 2019 | 35,3 | 35,4 | | 1° 2024 | 52,9 | 52,9 |
| 2° 2019 | 35,7 | 35,5 | | 2° 2024 | 38,1 | 38,1 |
| 1° 2020 | 40,8 | 40,9 | | 1° 2025 | 31,6 | 31,6 |
| 2° 2020 | 42,1 | 42,0 | | 2° 2025 | 28,4 | 28,2 |
| 1° 2021 | 40,4 | 40,6 | | 1° 2026 | — | 32,3 |
| 2° 2021 | 37,3 | 37,3 | | | | |

**Datos.** EPH, canastas por región y adultos equivalentes salen del espejo de [pyeph](https://github.com/reflejar/pyeph-data). Como el espejo se actualiza con retraso:

- Los trimestres de la EPH que el espejo no tiene se bajan directo del INDEC.
- La canasta de GBA se extiende con `serie_cba_cbt.xls` del INDEC y con `data/raw/indec/canastas/cba_cbt_gba.csv` (valores oficiales cargados a mano, como respaldo), validados contra los meses en común con el espejo.
- Las canastas de las otras regiones se publican con el informe semestral; hasta entonces, ese semestre no se calcula.
- Cada semestre se agrega la cifra oficial a `data/raw/indec/pobreza_oficial.csv`, que la página muestra junto a la réplica.

### Contrafactual: efecto de la canasta

Se repite la medición con canastas que, desde dic-2016, suben al mismo ritmo que el IPC nivel general. La diferencia con la pobreza medida es el efecto de que la canasta de los hogares pobres se encarezca más (o menos) que la inflación promedio. Mantiene fijos los ingresos y acumula desde dic-2016, así que el resultado depende de ese punto de partida.

### Vulnerabilidad

La población se reparte en siete estratos según el cociente entre su ingreso familiar y su línea de pobreza: indigentes, pobres no indigentes, tres franjas de vulnerables (hasta 10%, 10–25% y 25–50% por encima de la línea), entre 1,5 y 2 líneas, y más de 2 líneas. "Vulnerables" son las personas no pobres a menos de 50% de la línea. El umbral de 50% es una convención, por eso se publican las franjas por separado.

### Sesgo de medición por inflación

La EPH releva los ingresos del mes anterior a la entrevista. La serie "pobreza alineada" compara esos ingresos con la canasta del mismo mes. La diferencia con la pobreza medida crece casi linealmente con la inflación mensual: alrededor de 0,5 puntos de pobreza por cada punto de inflación (6,3 puntos en el 2° semestre de 2023). Es un ejercicio de sensibilidad: supone que todos los ingresos declarados corresponden al mes anterior y usa promedios trimestrales, porque la base pública no informa el mes de la entrevista.

## Distribución del ingreso

`src/indec/distribucion.py` calcula, por trimestre, el ingreso per cápita familiar (ingreso total familiar dividido por la cantidad de miembros del hogar) y lo ordena por personas ponderadas con `PONDIH`. Publica el coeficiente de Gini, el ingreso promedio y mediano (nominal y real), la participación de cada decil en el ingreso total y la brecha entre el decil 10 y el decil 1.

**Validación contra el INDEC:** Gini de 0,467 (1T-2024), 0,436 (2T-2024) y 0,424 (2T-2025), e ingreso per cápita promedio de $537.024 (2T-2025), idénticos a los oficiales. El script verifica los tres Gini en cada corrida y no guarda nada si alguno difiere en más de 0,003.

## Series de elaboración propia (`src/derivadas/calcular.py`)

| Serie | Cálculo |
|---|---|
| Tasa de interés real ex post | BADLAR de bancos privados (promedio mensual, convertida a tasa efectiva a 30 días) descontada por la inflación del mes siguiente, anualizada |
| Desvío del tipo de cambio real | ITCRM dividido por su promedio desde 1997, menos 1. Es una referencia histórica, no una estimación del tipo de cambio de equilibrio |
| Dolarización de depósitos privados | Depósitos privados en dólares (en pesos) sobre depósitos privados totales |
| Préstamos sobre depósitos | Préstamos al sector privado sobre depósitos privados |
| Base monetaria, M2 y préstamos en pesos reales | Promedio mensual deflactado por el IPC, en pesos del último mes disponible |

Series dadas de baja: el respaldo de la base monetaria y el tipo de cambio "de convertibilidad" usaban reservas brutas, que sobreestiman el respaldo efectivo. El "carry trade" medido al dólar oficial no era replicable durante el cepo. Están en la lista `RETIRADAS` de `calcular.py`, que las elimina de la base.

## Índice de Confianza en el Gobierno

Promedio, por ola mensual, de la variable `icg` de cada encuestado (escala 0 a 5), ponderado por `ponderacion_utdt`. El cálculo es idéntico a `opinAr::compute_icg`. Los componentes y los cortes por zona, sexo, edad y nivel educativo se calculan de la misma forma sobre cada subgrupo.

## Balance cambiario

Cada columna del anexo estadístico del BCRA tiene un código (`bal003`, `mlc010`, etc.). El nombre de la serie se arma con sus encabezados (por ejemplo, "Cuenta corriente cambiaria › Bienes › Cobros de exportaciones de bienes"). Se usan solo las filas mensuales: los totales anuales que el archivo trae debajo se descartan.

## REM

Cada serie se fecha por el mes de la encuesta, que cierra a fin de mes y se publica a comienzos del siguiente. "Inflación esperada para el mes de la encuesta" es el pronóstico hecho antes de que el INDEC publique ese dato, por lo que sirve para medir el error de pronóstico de los analistas.
