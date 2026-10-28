# Manual de mantenimiento

Guía para quien quede a cargo del proyecto. No hace falta saber programar para el mantenimiento habitual: casi todo corre solo y los problemas típicos se resuelven con unos clics.

## Qué es cada cosa

| Pieza | Dónde está | Para qué sirve |
|---|---|---|
| **Repositorio** | GitHub (este repo) | Código, datos (`datos/`) y documentación |
| **Actualización automática** | GitHub → pestaña **Actions** | Baja y valida los datos nuevos todos los lunes |
| **Base de datos** | [supabase.com](https://supabase.com) | Guarda las series que muestra la página |
| **Página web** | [share.streamlit.io](https://share.streamlit.io) | Publica la página a partir del código de `app/` |
| **Claves de la base** | GitHub → **Settings → Secrets and variables → Actions** (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`) | Permiten a la actualización escribir en la base |

Conviene que al menos dos personas del club tengan acceso de administrador a las tres cuentas (GitHub, Supabase y Streamlit), para que el proyecto no dependa de una sola.

## Qué corre solo

- **Todos los lunes a las 9:00:** el workflow *Actualizar datos* baja los datos nuevos, los valida, actualiza la base y la página, y regenera `datos/`. Tarda unos 5 minutos.
- **Todos los días a las 12:00:** el workflow *Mantener activa la base* hace una consulta mínima a Supabase, que pausa los proyectos gratuitos tras 7 días sin actividad.

## Revisión recomendada (5 minutos, una vez por semana o cada quince días)

1. **Actions → Actualizar datos:** la última corrida tiene que tener tilde verde ✅.
2. **Avisos amarillos:** al abrir la corrida, aparecen abajo, en *Annotations*. No son errores: indican que una serie no se pudo actualizar y se conservó su dato anterior. Ver qué hacer en la tabla de abajo.
3. **[`data/estado_actualizacion.json`](../data/estado_actualizacion.json):** la última fecha de cada fuente. Si alguna lleva meses sin moverse, revisar.

## Problemas frecuentes

| Qué aparece | Qué significa | Qué hacer |
|---|---|---|
| ❌ *"La base de datos no responde"* | Supabase pausó el proyecto o cambiaron las claves | Entrar a supabase.com → el proyecto → **Restore project**. Si no está pausado, revisar que los secrets del repo sigan siendo los de **Project Settings → API Keys** |
| ⚠️ *"no se pudo identificar la serie en la API (N candidatos: …)"* | Una serie de datos.gob.ar no tiene un ID fijo o el ID cambió | Elegir el candidato correcto de la lista y escribir su ID en el campo `id` de esa serie en [`src/datos_gob/catalogo.py`](../src/datos_gob/catalogo.py) (se puede editar desde la web de GitHub) |
| ⚠️ *"la fuente puede estar congelada"* | La fuente no publicó datos nuevos hace tiempo | Normal por unas semanas. Si sigue igual por meses, buscar en datos.gob.ar si la serie cambió de ID |
| ⚠️ *"la API no respondió a tiempo"* | Una fuente externa estuvo lenta o caída | Nada: es temporal y se conservan los datos anteriores |
| ⚠️ *"no coincide con la historia"* / *"no se guarda nada"* | La fuente cambió de formato o devolvió datos raros | Nada urgente: se conservan los datos anteriores. Si se repite, revisar el script de esa fuente en `src/` |
| ❌ Cruz roja en otro paso | Error de programación o cambio de formato grande | Abrir el paso con la cruz y leer las últimas líneas del error |
| La página no muestra lo último | La página guarda los datos 6 horas | Botón **🔄 Refrescar datos** de la página; si no alcanza, share.streamlit.io → la app → **⋮ → Reboot app** |

Para dónde mirar el detalle de cada serie: [`data/raw/datos_gob/ESTADO.csv`](../data/raw/datos_gob/ESTADO.csv) y `data/raw/internacional/ESTADO.csv` registran qué pasó con cada una en la última corrida.

## Tareas manuales

| Cuándo | Tarea | Cómo |
|---|---|---|
| **Cada semestre** (el INDEC publica pobreza a fines de marzo y de septiembre) | Cargar la cifra oficial | Agregar una fila a [`data/raw/indec/pobreza_oficial.csv`](../data/raw/indec/pobreza_oficial.csv): `semestre,pobreza,indigencia` con fecha `AAAA-01-01` (1° semestre) o `AAAA-07-01` (2°). Ejemplo: `2026-07-01,30.5,6.8` |
| **Solo si el aviso de canastas lo pide** | Cargar la canasta de GBA a mano | Agregar el mes a [`data/raw/indec/canastas/cba_cbt_gba.csv`](../data/raw/indec/canastas/cba_cbt_gba.csv) con los valores del comunicado del INDEC: `fecha,cba,cbt,fuente` |
| **Cuando cambian** | Bandas cambiarias, aperturas del IPC de la página | Reemplazar el archivo en `data/raw/bcra/tipo_de_cambio/` o `data/raw/indec/ipc/` y correr el workflow con **carga completa** tildada |

Los archivos se editan desde la web de GitHub: abrir el archivo → lápiz ✏️ → editar → **Commit changes**.

## Cambios habituales

- **Sumar una serie de datos.gob.ar:** una línea en [`src/datos_gob/catalogo.py`](../src/datos_gob/catalogo.py) (ver [CONTRIBUIR.md](../CONTRIBUIR.md)).
- **Mostrar en la página una fuente que hoy está solo en el repo:** sacar su nombre de `SOLO_REPO` en [`src/almacen.py`](../src/almacen.py). En la próxima corrida se sube a la base y aparece en *Explorar series*.
- **Sumar un indicador al resumen de la página:** agregar su `id` (ver [`datos/INDICE.csv`](../datos/INDICE.csv)) a la lista `RESUMEN` al principio de [`app/app.py`](../app/app.py).
- **Correr la actualización sin esperar al lunes:** Actions → Actualizar datos → **Run workflow**.

## Límites de las cuentas gratuitas

- **Supabase:** 500 MB de base. Hoy se usa una fracción; si alguna vez se llena, sacar fuentes de la página (agregarlas a `SOLO_REPO`).
- **GitHub Actions:** gratis e ilimitado en repositorios públicos.
- **Streamlit:** si nadie entra a la página por unos días, la app "se duerme" y el primer visitante tiene que tocar un botón para despertarla.
