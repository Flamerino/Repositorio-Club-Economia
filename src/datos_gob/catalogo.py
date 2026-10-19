"""Series que se traen de la API de Series de Tiempo (apis.datos.gob.ar).

Cada entrada:
  id      ID en la API, verificado en proyectos que lo usan en 2026 (ver fuente_id). Puede faltar.
  q       texto para buscar la serie si el ID no existe o no coincide.
  kw      palabras que TIENEN que aparecer en el título/descripción que devuelve la API
          (una tupla vale como "alguna de"). Protege contra IDs equivocados.
  kw_not  palabras que NO pueden aparecer.
  freq    frecuencia esperada: M, T (trimestral) o A.
  desde   recorte inicial (p. ej. series con cambios de moneda antes de 1992).
  dias    días máximos desde el FIN del último período con dato; si se supera, aviso de "serie congelada".
  exacto  expresión regular que debe cumplir el comienzo de la descripción (para no confundir un total
          con sus sub-rubros).
  calculo (serie_a, "+"/"-", serie_b): si la API no tiene la serie, se calcula con otras del catálogo.
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
         kw=[("emae", "estimador mensual"), "desestacionaliz"], kw_not=["variacion"],
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
         id="165.1_AAUH_0_0_3", q="asignacion universal por hijo monto",
         kw=["asignacion universal"], kw_not=["embarazo", "titulares", "cantidad"],
         fuente="ANSES", fuente_id="buscador de la API (corrida del 2026-10-15)"),

    # ------------------------------------------------------------------ fiscal (IMIG, base caja)
    dict(sid="mecon_resultado_primario", nombre="Resultado primario del Sector Público Nacional no financiero (base caja)",
         categoria="Fiscal", unidad="Millones de $", freq="M", dias=75,
         id="452.3_RESULTADO_RIO_0_M_18_54", q="IMIG resultado primario sector publico nacional mensual",
         kw=["resultado primario"], fuente="Secretaría de Hacienda (IMIG)",
         fuente_id="datosgobar/analisis-datos-python (notebook oficial); mau1878/REM"),
    dict(sid="mecon_resultado_financiero", nombre="Resultado financiero del Sector Público Nacional no financiero (base caja)",
         categoria="Fiscal", unidad="Millones de $", freq="M", dias=75,
         id="452.3_RESULTADO_ERO_0_M_20_25", q="IMIG resultado financiero", kw=["imig", "resultado financiero"],
         fuente="Secretaría de Hacienda (IMIG)", fuente_id="buscador de la API (corrida del 2026-10-15)"),
    dict(sid="mecon_ingresos_totales", nombre="Ingresos totales del Sector Público Nacional no financiero (base caja)",
         categoria="Fiscal", unidad="Millones de $", freq="M", dias=75,
         q="IMIG ingresos totales", kw=["imig", "ingresos totales"],
         exacto=r"^imig\. ingresos totales\s*(\||$)",  # solo el total, no sus sub-rubros
         fuente="Secretaría de Hacienda (IMIG)"),
    dict(sid="mecon_gasto_primario", nombre="Gasto primario del Sector Público Nacional no financiero (base caja)",
         categoria="Fiscal", unidad="Millones de $", freq="M", dias=75,
         q="IMIG gasto primario", kw=["imig", ("gasto primario", "gastos primarios")],
         exacto=r"^imig\. gastos? primarios?( totales?)?\s*(\||$)",
         calculo=("mecon_ingresos_totales", "-", "mecon_resultado_primario"),  # si la API no la tiene
         fuente="Secretaría de Hacienda (IMIG)",
         nota="Si la API no la publica, se calcula como ingresos totales menos resultado primario (identidad contable)."),
    dict(sid="mecon_intereses", nombre="Intereses netos de la deuda del Sector Público Nacional no financiero (base caja)",
         categoria="Fiscal", unidad="Millones de $", freq="M", dias=75,
         id="452.3_INTERESES_TOS_0_M_15_62", q="IMIG intereses netos", kw=["imig", "intereses"],
         fuente="Secretaría de Hacienda (IMIG)", fuente_id="buscador de la API (corrida del 2026-10-15)"),
    # ------------------------------------------------------------------ actividad (sectores y PBI)
    dict(sid="indec_pib_trimestral", nombre="PIB a precios de 2004, serie original (trimestral)",
         categoria="Actividad", unidad="Millones de $ de 2004", freq="T", dias=200,
         id="9.2_PP2_2004_T_16", q="PIB a precios constantes 2004 en millones de pesos",
         kw=[("pib", "producto interno bruto"), "constantes", "2004"], kw_not=["desestacionaliz", "implicit", "corrientes"],
         fuente="INDEC", fuente_id="buscador de la API (corrida del 2026-10-15)"),
    dict(sid="indec_ipi", nombre="IPI manufacturero, desestacionalizado",
         categoria="Actividad", unidad="Índice", freq="M", dias=110,
         id="453.1_SERIE_DESEADA_0_0_24_58", q="IPI manufacturero nivel general desestacionalizado",
         kw=[("ipi", "industrial"), "desestacionaliz"], fuente="INDEC",
         fuente_id="Juanpintoselso33/cigob-informe-coyuntura (2026)"),
    dict(sid="indec_isac", nombre="ISAC: actividad de la construcción, nivel general",
         categoria="Actividad", unidad="Índice", freq="M", dias=110,
         id="33.2_ISAC_NIVELRAL_0_M_18_63", q="ISAC indicador sintetico actividad construccion nivel general",
         kw=[("isac", "construccion")], fuente="INDEC", fuente_id="joacoabraldes/downloader (2026)"),

    # ------------------------------------------------------------------ sector externo
    dict(sid="indec_exportaciones", nombre="Exportaciones de bienes (ICA)",
         categoria="Sector externo", unidad="Millones de USD", freq="M", dias=120,
         id="74.3_IET_0_M_16", q="exportaciones intercambio comercial argentino mensual total",
         kw=["exportaciones"], fuente="INDEC", fuente_id="mau1878/REM",
         nota="La API suele ir unas semanas detrás de la publicación del INDEC."),
    dict(sid="indec_importaciones", nombre="Importaciones de bienes (ICA)",
         categoria="Sector externo", unidad="Millones de USD", freq="M", dias=120,
         id="74.3_IIT_0_M_25", q="importaciones intercambio comercial argentino mensual total",
         kw=["importaciones"], fuente="INDEC", fuente_id="mau1878/REM",
         nota="La API suele ir unas semanas detrás de la publicación del INDEC."),

    # ------------------------------------------------------------------ mercado de trabajo
    dict(sid="indec_desocupacion", nombre="Tasa de desocupación (EPH, 31 aglomerados)",
         categoria="Mercado de trabajo", unidad="%", freq="T", dias=200,
         id="45.2_ECTDT_0_T_33", q="tasa de desocupacion total EPH trimestral",
         kw=[("desocupacion", "desempleo")], fuente="INDEC", fuente_id="mau1878/REM; colossus-lab/openarg_backend"),
    dict(sid="indec_informalidad", nombre="Asalariados sin descuento jubilatorio (informalidad)",
         categoria="Mercado de trabajo", unidad="%", freq="T", dias=200,
         id="52.2_ASDJ_0_0_37", q="asalariados sin descuento jubilatorio trimestral",
         kw=[("jubilatorio", "descuento")], fuente="INDEC", fuente_id="Juanpintoselso33/cigob-informe-coyuntura (2026)"),
    dict(sid="trabajo_empleo_registrado", nombre="Trabajadores asalariados registrados (SIPA)",
         categoria="Mercado de trabajo", unidad="Miles de personas", freq="M", dias=120,
         id="151.1_AARIADODAD_2012_M_31", q="asalariados sector privado sin estacionalidad total pais",
         kw=["asalariados", "sector privado"], kw_not=["provincia", "rama", "region"],
         fuente="Secretaría de Trabajo (SIPA)",
         fuente_id="Juanpintoselso33/cigob-informe-coyuntura (2026)"),

    # ------------------------------------------------------------------ precios (aperturas del IPC y canastas)
    dict(sid="indec_ipc_nucleo_auto", nombre="IPC núcleo (Total nacional, dic-2016=100)",
         categoria="Precios", unidad="Índice", freq="M", dias=75,
         id="148.3_INUCLEONAL_DICI_M_19", q="IPC nucleo nacional base diciembre 2016",
         kw=["nucleo"], kw_not=["gba"], fuente="INDEC", fuente_id="mau1878/REM",
         nota="Versión automática de la apertura que también está en data/processed/indec (archivo manual)."),
    dict(sid="indec_ipc_regulados_auto", nombre="IPC regulados (Total nacional, dic-2016=100)",
         categoria="Precios", unidad="Índice", freq="M", dias=75,
         id="148.3_IREGULANAL_DICI_M_22", q="IPC regulados nacional base diciembre 2016",
         kw=["regulad"], kw_not=["gba"], fuente="INDEC", fuente_id="Juanpintoselso33/cigob-informe-coyuntura (2026)"),
    dict(sid="indec_ipc_alimentos_auto", nombre="IPC alimentos y bebidas no alcohólicas (Total nacional, dic-2016=100)",
         categoria="Precios", unidad="Índice", freq="M", dias=75,
         id="146.3_IALIMENNAL_DICI_M_45", q="IPC alimentos y bebidas no alcoholicas nacional",
         kw=["alimentos"], kw_not=["gba"], fuente="INDEC", fuente_id="Juanpintoselso33/cigob-informe-coyuntura (2026)"),
    dict(sid="indec_ipc_vivienda_auto", nombre="IPC vivienda, agua, electricidad, gas y otros combustibles (Total nacional)",
         categoria="Precios", unidad="Índice", freq="M", dias=75,
         id="146.3_IVIVIENNAL_DICI_M_52", q="IPC vivienda agua electricidad gas nacional",
         kw=["vivienda"], kw_not=["gba", "alquiler"], fuente="INDEC",
         fuente_id="Juanpintoselso33/cigob-informe-coyuntura (2026)"),
    dict(sid="indec_cba_gba_auto", nombre="Canasta Básica Alimentaria, adulto equivalente (GBA)",
         categoria="Precios", unidad="$", freq="M", dias=75,
         id="150.1_CSTA_BARIA_0_D_26", q="canasta basica alimentaria adulto equivalente",
         kw=[("canasta basica alimentaria", "cba")], fuente="INDEC",
         fuente_id="Juanpintoselso33/cigob-informe-coyuntura (2026)"),
    dict(sid="indec_cbt_gba_auto", nombre="Canasta Básica Total, adulto equivalente (GBA)",
         categoria="Precios", unidad="$", freq="M", dias=75,
         id="150.1_CSTA_BATAL_0_D_20", q="canasta basica total adulto equivalente",
         kw=[("canasta basica total", "cbt")], fuente="INDEC",
         fuente_id="Juanpintoselso33/cigob-informe-coyuntura (2026)"),
]

# CSV del INDEC con el índice de salarios: URL fija; separador ';', coma decimal, fecha d/m/aaaa, BOM.
CSV_SALARIOS = "https://www.indec.gob.ar/ftp/cuadros/sociedad/indice_salarios.csv"
