"""Series que se traen de la API de Series de Tiempo (apis.datos.gob.ar).

Cada entrada:
  id      ID en la API, verificado en proyectos que lo usan en 2026 (ver fuente_id). Puede faltar.
  q       texto para buscar la serie si el ID no existe o no coincide.
  kw      palabras que TIENEN que aparecer en el título/descripción que devuelve la API
          (una tupla vale como "alguna de"). Protege contra IDs equivocados.
  kw_not  palabras que NO pueden aparecer.
  freq    frecuencia esperada: M, T (trimestral) o A.
  desde   recorte inicial (p. ej. series con cambios de moneda antes de 1992).
  dias    edad máxima razonable del último dato; si se supera, queda un aviso de "serie congelada".
"""

SERIES = [
    # ------------------------------------------------------------------ actividad
    dict(sid="indec_emae", nombre="EMAE: Estimador Mensual de Actividad Económica, serie original (2004=100)",
         categoria="Actividad", unidad="Índice", freq="M", dias=110,
         id="143.3_NO_PR_2004_A_21", q="EMAE nivel general serie original",
         kw=[("emae", "estimador mensual")], kw_not=["desestacionaliz", "tendencia"],
         fuente="INDEC", fuente_id="datosgobar/series-tiempo-ar-api (ejemplo oficial); gauss314/skills"),
    dict(sid="indec_emae_desest", nombre="EMAE desestacionalizado (2004=100)",
         categoria="Actividad", unidad="Índice", freq="M", dias=110,
         id="143.3_NO_PR_2004_A_31", q="EMAE nivel general desestacionalizado",
         kw=[("emae", "estimador mensual"), "desestacionaliz"],
         fuente="INDEC", fuente_id="gauss314/skills (verificado 2026-06)"),

    # ------------------------------------------------------------------ salarios e ingresos
    # Índice de salarios: fuente principal el CSV del INDEC (ver CSV_SALARIOS); la API es respaldo
    # porque llegó a estar 162 días sin actualizarse (documentado en joacoabraldes/downloader).
    dict(sid="indec_salarios_total", nombre="Índice de salarios: nivel general (oct-2016=100)",
         categoria="Salarios e ingresos", unidad="Índice", freq="M", dias=150, csv="IS_indice_total",
         id="149.1_TL_INDIIOS_OCTU_0_21", kw=["salario"], fuente="INDEC"),
    dict(sid="indec_salarios_registrado", nombre="Índice de salarios: empleo registrado (oct-2016=100)",
         categoria="Salarios e ingresos", unidad="Índice", freq="M", dias=150, csv="IS_total_registrado",
         id="149.1_TL_REGIADO_OCTU_0_16", kw=["salario", "registrado"], fuente="INDEC"),
    dict(sid="indec_salarios_privado_registrado", nombre="Índice de salarios: sector privado registrado (oct-2016=100)",
         categoria="Salarios e ingresos", unidad="Índice", freq="M", dias=150, csv="IS_sector_privado_registrado",
         id="149.1_SOR_PRIADO_OCTU_0_25", kw=["salario", "privado"], kw_not=["no registrado"], fuente="INDEC"),
    dict(sid="indec_salarios_publico", nombre="Índice de salarios: sector público (oct-2016=100)",
         categoria="Salarios e ingresos", unidad="Índice", freq="M", dias=150, csv="IS_sector_publico",
         id="149.1_SOR_PUBICO_OCTU_0_14", kw=["salario", "publico"], fuente="INDEC"),
    dict(sid="indec_salarios_no_registrado", nombre="Índice de salarios: sector privado no registrado (oct-2016=100)",
         categoria="Salarios e ingresos", unidad="Índice", freq="M", dias=200, csv="IS_sector_no_registrado",
         id="149.1_SOR_PRIADO_OCTU_0_28", kw=["salario", "no registrado"], fuente="INDEC",
         nota="El INDEC lo publica con 5 meses de rezago."),
    dict(sid="trabajo_ripte", nombre="RIPTE: Remuneración Imponible Promedio de los Trabajadores Estables",
         categoria="Salarios e ingresos", unidad="$", freq="M", dias=120,
         id="158.1_REPTE_0_0_5", q="RIPTE remuneracion imponible promedio trabajadores estables",
         kw=[("ripte", "remuneracion imponible")], fuente="Secretaría de Trabajo"),
    dict(sid="trabajo_smvm", nombre="Salario Mínimo, Vital y Móvil (mensual)",
         categoria="Salarios e ingresos", unidad="$", freq="M", dias=90, desde="1992-01-01",
         id="57.1_SMVMM_0_M_34", q="salario minimo vital y movil mensual",
         kw=[("salario minimo", "smvm")], kw_not=["diario", "horario"], fuente="Secretaría de Trabajo",
         nota="Incluye meses futuros ya fijados por decreto. Antes de 1992 la serie está en otras monedas "
              "(australes, pesos argentinos), por eso se recorta."),

    # ------------------------------------------------------------------ jubilaciones y transferencias
    dict(sid="anses_haber_minimo", nombre="Haber mínimo jubilatorio",
         categoria="Jubilaciones y transferencias", unidad="$", freq="M", dias=120, desde="1992-01-01",
         id="58.1_MP_0_M_13", q="haber minimo jubilatorio",
         kw=[("haber minimo", "jubilator")], fuente="ANSES / Secretaría de Seguridad Social",
         nota="No incluye el bono previsional que se paga aparte. Recortada desde 1992 por los cambios de moneda."),
    dict(sid="anses_auh", nombre="Asignación Universal por Hijo (monto por hijo)",
         categoria="Jubilaciones y transferencias", unidad="$", freq="M", dias=120,
         q="asignacion universal por hijo monto", kw=["asignacion universal"], kw_not=["embarazo", "titulares", "cantidad"],
         fuente="ANSES"),

    # ------------------------------------------------------------------ fiscal (IMIG, base caja)
    dict(sid="mecon_resultado_primario", nombre="Resultado primario del Sector Público Nacional no financiero (base caja)",
         categoria="Fiscal", unidad="Millones de $", freq="M", dias=75,
         id="452.3_RESULTADO_RIO_0_M_18_54", q="IMIG resultado primario sector publico nacional mensual",
         kw=["resultado primario"], fuente="Secretaría de Hacienda (IMIG)",
         fuente_id="datosgobar/analisis-datos-python (notebook oficial); mau1878/REM"),
    dict(sid="mecon_resultado_financiero", nombre="Resultado financiero del Sector Público Nacional no financiero (base caja)",
         categoria="Fiscal", unidad="Millones de $", freq="M", dias=75,
         q="IMIG resultado financiero sector publico nacional mensual", kw=["resultado financiero"],
         fuente="Secretaría de Hacienda (IMIG)"),
    dict(sid="mecon_ingresos_totales", nombre="Ingresos totales del Sector Público Nacional no financiero (base caja)",
         categoria="Fiscal", unidad="Millones de $", freq="M", dias=75,
         q="IMIG ingresos totales sector publico nacional mensual", kw=[("ingresos totales", "recursos totales")],
         fuente="Secretaría de Hacienda (IMIG)"),
    dict(sid="mecon_gasto_primario", nombre="Gasto primario del Sector Público Nacional no financiero (base caja)",
         categoria="Fiscal", unidad="Millones de $", freq="M", dias=75,
         q="IMIG gasto primario sector publico nacional mensual", kw=[("gasto primario", "gastos primarios")],
         fuente="Secretaría de Hacienda (IMIG)"),
    dict(sid="mecon_intereses", nombre="Intereses de la deuda del Sector Público Nacional no financiero (base caja)",
         categoria="Fiscal", unidad="Millones de $", freq="M", dias=75,
         q="IMIG intereses deuda sector publico nacional mensual", kw=["intereses"], kw_not=["intrasector"],
         fuente="Secretaría de Hacienda (IMIG)"),
]

# CSV del INDEC con el índice de salarios: URL fija; separador ';', coma decimal, fecha d/m/aaaa, BOM.
CSV_SALARIOS = "https://www.indec.gob.ar/ftp/cuadros/sociedad/indice_salarios.csv"
