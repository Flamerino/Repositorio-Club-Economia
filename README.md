# Datos económicos de Argentina · Club de Economía UADE

Base de datos abierta y reproducible sobre la economía argentina: series oficiales de BCRA, INDEC, Ministerio de Economía y otros organismos, contexto internacional y series de elaboración propia del Club. Todo se actualiza automáticamente cada semana y cada cifra puede rastrearse hasta su fuente.

**[📂 Datos](datos/)** · **[🌐 Página web](https://club-economia-uade.streamlit.app/)** · **[📑 Fuentes](docs/FUENTES.md)** · **[📐 Metodología](docs/METODOLOGIA.md)** · **[⚙️ Arquitectura](docs/ARQUITECTURA.md)** · **[🤝 Cómo contribuir](CONTRIBUIR.md)**

## Qué hay

Más de 550 series, cada una en su propio archivo CSV (`fecha, valor`) dentro de [`datos/`](datos/), ordenadas por fuente y tema. El catálogo completo, con unidad, frecuencia, período y descripción de cada serie, está en [`datos/INDICE.csv`](datos/INDICE.csv).

| Área | Contenido | Fuentes |
|---|---|---|
| Moneda y bancos | Reservas, base monetaria, depósitos, préstamos, tasas, instrumentos del BCRA | BCRA |
| Dólar y sector externo | Balance cambiario, mercado de cambios, tipo de cambio real, oficial, MEP, CCL, blue, brechas, riesgo país, balanza de pagos, comercio exterior | BCRA, INDEC, ArgentinaDatos |
| Actividad | EMAE, PIB trimestral, industria (IPI), construcción (ISAC) | INDEC |
| Precios | IPC y aperturas, canastas básicas por región | INDEC |
| Trabajo e ingresos | Salarios, RIPTE, salario mínimo, jubilación mínima, AUH, desocupación, informalidad, empleo registrado | INDEC, Secretaría de Trabajo, ANSES |
| Fiscal | Resultado primario y financiero, ingresos, gasto primario, intereses | Secretaría de Hacienda |
| Pobreza y distribución | Pobreza, indigencia, vulnerabilidad, Gini, participación por decil | Elaboración propia con EPH (INDEC) |
| Expectativas y opinión | Expectativas de analistas (REM), Índice de Confianza en el Gobierno | BCRA, Universidad Torcuato Di Tella |
| Contexto internacional | Comparación con la región, proyecciones del FMI, Fed y commodities, Brasil, PIB per cápita histórico | Banco Mundial, FMI, FRED, Banco Central de Brasil, Proyecto Maddison |

## Cómo usar los datos

Cada archivo se puede abrir en Excel o Google Sheets, o leer directo desde GitHub:

```python
import pandas as pd

url = "https://raw.githubusercontent.com/Flamerino/Repositorio-Club-Economia/main/datos/bcra/reservas/saldo_de_reservas_internacionales.csv"
reservas = pd.read_csv(url, parse_dates=["fecha"])
```

## Calidad de los datos

- **Fuentes oficiales primero.** Las fuentes no oficiales (cotizaciones del dólar paralelo) están marcadas como tales y se validan contra un dato oficial.
- **Validación antes de guardar.** Cada fuente se compara contra un dato conocido antes de escribir: la historia ya guardada, otra fuente oficial o una cifra publicada. Si no coincide, no se carga nada y la corrida deja un aviso.
- **Réplicas verificadas.** Pobreza, indigencia y Gini se calculan con los microdatos de la EPH y coinciden con las cifras oficiales del INDEC (diferencias de 0,2 puntos o menos; ver [metodología](docs/METODOLOGIA.md)).
- **Trazabilidad.** El índice indica para cada serie su origen exacto (ID en la API, archivo y columna) y el código que la produce está en [`src/`](src/).

## Actualización

Un workflow de GitHub Actions corre todos los lunes: descarga los datos nuevos, los valida, recalcula las series propias, actualiza la base de datos de la página y regenera [`datos/`](datos/). La última fecha disponible de cada fuente queda registrada en [`data/estado_actualizacion.json`](data/estado_actualizacion.json).

## Estructura del repositorio

```
datos/          Una serie por archivo, lista para usar (se genera automáticamente)
data/raw/       Archivos originales, tal como los publica cada fuente
src/            Código: descarga, validación, limpieza y cálculo de cada fuente
app/            Página web (Streamlit)
db/             Esquema de la base de datos (Supabase)
docs/           Fuentes, metodología y arquitectura
```

## Uso y créditos

Los datos pertenecen a sus respectivas fuentes, que se citan en [`docs/FUENTES.md`](docs/FUENTES.md) y en el índice. Al usarlos, citar la fuente original y este repositorio. Proyecto del área de *Policy and Public Impact* del Club de Economía de la Universidad Argentina de la Empresa (UADE).
