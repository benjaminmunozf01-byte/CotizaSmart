"""
Pruebas unitarias y de integración (pytest) para el motor Montecarlo de CotizaSmart.
Trabajo 3 - Tecnología de la Información II, Universidad de Concepción (Campus Los Ángeles).
Autores: Jorge Campos, Benjamin Muñoz y Raul Vergara.
"""

from pathlib import Path
import sys
import numpy as np
import pytest

# Asegurar que la raíz de CotizaSmart esté en sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from motor_calculo import (
    ErrorValidacionCotizacion,
    calcular_probabilidad_ganar,
    evaluar_precio_puntual,
    limpiar_numero_chileno,
    muestrear_pert_vectorizado,
    procesar_csv_base_costos,
    procesar_csv_calibracion,
    simular_cotizacion,
)
from seed import asegurar_archivos_csv_ejemplo, obtener_plantilla_electrica


def test_distribucion_pert_media_y_cotas():
    """
    Verifica que el muestreo PERT vectorizado respete estrictamente las cotas [min, max]
    y que su media empírica converja a la media teórica (min + 4*prob + max) / 6.
    """
    rng = np.random.default_rng(12345)
    v_min, v_prob, v_max = 1000.0, 1400.0, 2600.0
    media_teorica = (v_min + 4.0 * v_prob + v_max) / 6.0  # 1533.33

    muestras = muestrear_pert_vectorizado(v_min, v_prob, v_max, n_sim=20000, rng=rng)
    assert muestras.shape == (20000,)
    assert np.all(muestras >= v_min)
    assert np.all(muestras <= v_max)
    assert abs(float(np.mean(muestras)) - media_teorica) < 15.0


def test_precio_optimo_existe_y_maximiza_ganancia():
    """
    Verifica que el precio óptimo exista dentro de la grilla evaluada y que maximice
    la ganancia esperada respecto a cualquier otro punto de la grilla.
    """
    partidas = obtener_plantilla_electrica()
    resultado = simular_cotizacion(partidas, semilla=42)

    curva = resultado["curva_precio_optimo"]
    precios = np.array(curva["precios_clp"])
    ganancias = np.array(curva["ganancia_esperada_clp"])
    idx_opt = curva["indice_optimo"]

    assert 0 <= idx_opt < len(precios)
    assert resultado["resumen"]["precio_optimo_clp"] == precios[idx_opt]
    assert ganancias[idx_opt] == np.max(ganancias)
    assert ganancias[idx_opt] > 0


def test_probabilidad_perdida_disminuye_al_subir_precio():
    """
    Verifica que P(pérdida) sea monótonamente decreciente (no creciente) a medida que
    sube el precio ofertado, y estrictamente menor en el extremo superior que en el inferior.
    """
    partidas = obtener_plantilla_electrica()
    resultado = simular_cotizacion(partidas, semilla=42)

    probs_perdida = np.array(resultado["curva_precio_optimo"]["prob_perdida_pct"])
    diferencias = np.diff(probs_perdida)

    assert np.all(diferencias <= 1e-6)
    assert probs_perdida[-1] < probs_perdida[0]
    p_seguro = resultado["resumen"]["precio_min_seguro_clp"]
    res_seguro = simular_cotizacion(
        partidas, semilla=42, precio_ofertado_usuario=p_seguro
    )
    assert res_seguro["evaluacion_ofertado"]["prob_perdida_pct"] <= 10.0


def test_sistema_no_falla_con_una_sola_partida():
    """
    Verifica que el motor funcione sin errores cuando la cotización tiene una única partida.
    """
    unica_partida = [
        {
            "categoria": "materiales",
            "descripcion": "Tablero eléctrico monofásico completo",
            "unidad": "un",
            "cantidad": 1,
            "valor_min": 180000,
            "valor_prob": 210000,
            "valor_max": 290000,
            "merma_pct": 5.0,
            "sensible_cobre": True,
            "sensible_dolar": True,
        }
    ]
    resultado = simular_cotizacion(unica_partida, semilla=99)
    assert resultado["resumen"]["costo_esperado_clp"] > 180000
    assert resultado["resumen"]["precio_optimo_clp"] > resultado["resumen"]["costo_esperado_clp"]
    assert len(resultado["ranking_riesgo"]) == 1
    assert resultado["ranking_riesgo"][0]["aporte_riesgo_pct"] == 100.0


def test_calibracion_demo_ingenuo_amarillo_y_optimo_verde():
    """
    Verifica el requisito de negocio para la cotización demo de Los Ángeles:
    - Precio ingenuo (costo esperado + 20%) muestra semáforo amarillo o rojo (P(pérdida) >= 10%).
    - Precio óptimo muestra semáforo verde (P(pérdida) < 10%).
    - Margen óptimo sobre costo esperado está entre 10% y 30%.
    - Tiempo de ejecución < 2000 ms (2 segundos).
    """
    partidas = obtener_plantilla_electrica()
    resultado = simular_cotizacion(
        partidas=partidas,
        gg_min=9.0,
        gg_prob=12.0,
        gg_max=22.0,
        semilla=42,
    )

    ev_ingenuo = resultado["evaluacion_ingenuo"]
    ev_optimo = resultado["evaluacion_optimo"]

    assert ev_ingenuo["semaforo"] in ("amarillo", "rojo")
    assert ev_ingenuo["prob_perdida_pct"] >= 10.0

    assert ev_optimo["semaforo"] == "verde"
    assert ev_optimo["prob_perdida_pct"] < 10.0
    assert 10.0 <= ev_optimo["margen_sobre_costo_pct"] <= 30.0
    assert resultado["resumen"]["tiempo_calculo_ms"] < 2000.0


def test_sensibilidad_independiente_cobre_y_dolar():
    """
    Verifica que:
    1. La plantilla eléctrica tenga marcadas como 'sensible_dolar' las luminarias LED,
       tableros y protecciones importadas.
    2. El slider de dólar afecte SOLO a las partidas marcadas con sensible_dolar=True.
    3. El slider de cobre afecte SOLO a las partidas marcadas con sensible_cobre=True.
    """
    plantilla = obtener_plantilla_electrica()
    descripciones_dolar = [p["descripcion"].lower() for p in plantilla if p.get("sensible_dolar")]
    assert any("led" in d for d in descripciones_dolar)
    assert any("tablero" in d for d in descripciones_dolar)
    assert any("termomagnéticos" in d or "diferenciales" in d for d in descripciones_dolar)

    # Partida solo sensible al cobre vs partida solo sensible al dólar
    partida_solo_cobre = [
        {
            "categoria": "materiales",
            "descripcion": "Cable THHN Cobre Puro",
            "unidad": "m",
            "cantidad": 100,
            "valor_min": 1000,
            "valor_prob": 1000,
            "valor_max": 1000,
            "merma_pct": 0.0,
            "sensible_cobre": True,
            "sensible_dolar": False,
        }
    ]
    partida_solo_dolar = [
        {
            "categoria": "materiales",
            "descripcion": "Panel Luminaria LED Importada",
            "unidad": "un",
            "cantidad": 10,
            "valor_min": 20000,
            "valor_prob": 20000,
            "valor_max": 20000,
            "merma_pct": 0.0,
            "sensible_cobre": False,
            "sensible_dolar": True,
        }
    ]

    # Mover solo el dólar NO debe alterar la partida que solo es sensible al cobre
    cobre_base = simular_cotizacion(
        partida_solo_cobre, var_cobre=0, var_dolar=0, gg_min=0, gg_prob=0, gg_max=0, semilla=1
    )["resumen"]["costo_esperado_clp"]
    cobre_con_dolar = simular_cotizacion(
        partida_solo_cobre, var_cobre=0, var_dolar=15, gg_min=0, gg_prob=0, gg_max=0, semilla=1
    )["resumen"]["costo_esperado_clp"]
    cobre_con_cobre = simular_cotizacion(
        partida_solo_cobre, var_cobre=20, var_dolar=0, gg_min=0, gg_prob=0, gg_max=0, semilla=1
    )["resumen"]["costo_esperado_clp"]

    assert cobre_con_dolar == cobre_base
    assert cobre_con_cobre > cobre_base

    # Mover solo el cobre NO debe alterar la partida que solo es sensible al dólar
    dolar_base = simular_cotizacion(
        partida_solo_dolar, var_cobre=0, var_dolar=0, gg_min=0, gg_prob=0, gg_max=0, semilla=1
    )["resumen"]["costo_esperado_clp"]
    dolar_con_cobre = simular_cotizacion(
        partida_solo_dolar, var_cobre=25, var_dolar=0, gg_min=0, gg_prob=0, gg_max=0, semilla=1
    )["resumen"]["costo_esperado_clp"]
    dolar_con_dolar = simular_cotizacion(
        partida_solo_dolar, var_cobre=0, var_dolar=15, gg_min=0, gg_prob=0, gg_max=0, semilla=1
    )["resumen"]["costo_esperado_clp"]

    assert dolar_con_cobre == dolar_base
    assert dolar_con_dolar > dolar_base


def test_formatos_numericos_csv_y_descarte_filas():
    """
    Verifica que limpiar_numero_chileno y los lectores CSV con dtype=str:
    1. Acepten '12500000', '12.500.000', '$12.500.000', '12500000.50' y '12.500.000,50'
       sin alterar el valor.
    2. Descarten filas con celdas vacías o no numéricas e informen exactamente cuántas
       filas fueron descartadas en competencia, historial y base de costos.
    """
    assert limpiar_numero_chileno("12500000") == 12500000.0
    assert limpiar_numero_chileno("12.500.000") == 12500000.0
    assert limpiar_numero_chileno("$12.500.000") == 12500000.0
    assert limpiar_numero_chileno("12500000.50") == 12500000.50
    assert limpiar_numero_chileno("12.500.000,50") == 12500000.50
    assert limpiar_numero_chileno("") is None
    assert limpiar_numero_chileno("no_numerico") is None

    # 1. CSV Competencia con los 5 formatos + 2 filas inválidas (vacía y texto)
    csv_comp = (
        "proyecto;rubro;superficie_m2;precio_adjudicado;region;fecha\n"
        "Obra 1;Eléctrico;100;12500000;Biobío;01-10-2026\n"
        "Obra 2;Eléctrico;100;12.500.000;Biobío;02-10-2026\n"
        "Obra 3;Eléctrico;100;$12.500.000;Biobío;03-10-2026\n"
        "Obra 4;Eléctrico;100;12500000.50;Biobío;04-10-2026\n"
        "Obra 5;Eléctrico;100;12.500.000,50;Biobío;05-10-2026\n"
        "Obra Invalida 1;Eléctrico;100;;Biobío;06-10-2026\n"
        "Obra Invalida 2;Eléctrico;abc;12500000;Biobío;07-10-2026\n"
    ).encode("utf-8")
    res_comp = procesar_csv_calibracion(csv_comp, "comp_formatos.csv")
    assert res_comp["n_registros"] == 5
    assert res_comp["filas_descartadas"] == 2
    assert res_comp["precios_adjudicados"] == [
        12500000.0,
        12500000.0,
        12500000.0,
        12500000.5,
        12500000.5,
    ]

    # 2. CSV Historial con formatos variados + 2 filas inválidas
    csv_hist = (
        "proyecto;costo_estimado;precio_ofertado;resultado\n"
        "H1;10000000;12500000;1\n"
        "H2;10.000.000;12.500.000;1\n"
        "H3;$10.000.000;$12.500.000;0\n"
        "H4;10000000.50;12500000.50;0\n"
        "H5;10.000.000,50;12.500.000,50;1\n"
        "H_vacia;10000000;;1\n"
        "H_texto;diez_millones;12500000;0\n"
    ).encode("utf-8")
    res_hist = procesar_csv_calibracion(csv_hist, "hist_formatos.csv")
    assert res_hist["n_registros"] == 5
    assert res_hist["filas_descartadas"] == 2

    # 3. CSV Base de costos con formatos variados + 2 filas inválidas
    csv_costos = (
        "descripcion;unidad;precio_min;precio_probable;precio_max\n"
        "Item 1;gl;12500000;12.500.000;$12.500.000\n"
        "Item 2;gl;12500000.50;12.500.000,50;13.000.000,00\n"
        "Item Vacio;gl;1000;;2000\n"
        "Item Texto;gl;mil;2000;3000\n"
    ).encode("utf-8")
    partidas_leidas = procesar_csv_base_costos(csv_costos)
    assert len(partidas_leidas) == 2
    assert partidas_leidas.filas_descartadas == 2
    assert partidas_leidas[0]["valor_min"] == 12500000.0
    assert partidas_leidas[0]["valor_prob"] == 12500000.0
    assert partidas_leidas[0]["valor_max"] == 12500000.0
    assert partidas_leidas[1]["valor_min"] == 12500000.50
    assert partidas_leidas[1]["valor_prob"] == 12500000.50


def test_calibracion_competencia_normalizada_por_m2_y_aviso_sin_m2():
    """
    Verifica que:
    1. Si el CSV de competencia trae 'superficie_m2', normalice a precio/m² y funcione
       coherentemente en un proyecto de otro tamaño (ej: 360 m², 3 veces más grande).
    2. Si el CSV NO trae 'superficie_m2', muestre el aviso exacto:
       'Los precios no se normalizaron por tamaño; úsalos solo con obras de monto similar'
       y limite P(win) con un piso razonable (>= 10%) en lugar de caer a 1%.
    """
    partidas_120 = obtener_plantilla_electrica()
    res_120 = simular_cotizacion(partidas_120, superficie_m2=120.0, semilla=42)
    rutas = asegurar_archivos_csv_ejemplo(
        costo_ref_clp=res_120["resumen"]["costo_esperado_clp"], superficie_ref_m2=120.0
    )

    cal_con_m2 = procesar_csv_calibracion(rutas["competencia"].read_bytes(), "comp_m2.csv")
    assert cal_con_m2["normalizado_m2"] is True
    assert cal_con_m2["aviso_tamano"] is None

    # Crear un proyecto 3 veces más grande (360 m²) escalando cantidades x3
    partidas_360 = []
    for p in partidas_120:
        copia = dict(p)
        if copia["categoria"] != "imprevistos":
            copia["cantidad"] = copia["cantidad"] * 3
        partidas_360.append(copia)

    sim_120_cal = simular_cotizacion(
        partidas_120, superficie_m2=120.0, calibracion=cal_con_m2, semilla=42
    )
    sim_360_cal = simular_cotizacion(
        partidas_360, superficie_m2=360.0, calibracion=cal_con_m2, semilla=42
    )

    # Gracias a la normalización por m², el proyecto de 360 m² (que cuesta ~31,6M CLP)
    # mantiene un margen óptimo sobre costo y una probabilidad de ganar equivalentes al de 120 m²
    assert 15.0 <= sim_360_cal["evaluacion_optimo"]["margen_sobre_costo_pct"] <= 30.0
    assert abs(
        sim_360_cal["evaluacion_optimo"]["prob_ganar_licitacion_pct"]
        - sim_120_cal["evaluacion_optimo"]["prob_ganar_licitacion_pct"]
    ) < 5.0

    # Ahora probar un CSV de competencia SIN columna superficie_m2
    csv_sin_m2 = (
        "proyecto,rubro,precio_adjudicado,region,fecha\n"
        "Obra A,Eléctrico,9500000,Biobío,01-10-2026\n"
        "Obra B,Eléctrico,10500000,Biobío,02-10-2026\n"
        "Obra C,Eléctrico,11500000,Biobío,03-10-2026\n"
        "Obra D,Eléctrico,12500000,Biobío,04-10-2026\n"
    ).encode("utf-8")
    cal_sin_m2 = procesar_csv_calibracion(csv_sin_m2, "sin_m2.csv")
    assert cal_sin_m2["normalizado_m2"] is False
    assert (
        cal_sin_m2["aviso_tamano"]
        == "Los precios no se normalizaron por tamaño; úsalos solo con obras de monto similar"
    )

    # Incluso para un precio muy alto (35 millones), P(win) tiene un piso razonable (>= 10%), no 1%
    p_win_alto = float(
        calcular_probabilidad_ganar(35000000.0, 10000000.0, cal_sin_m2, superficie_m2=360.0)
    )
    assert p_win_alto >= 0.10


def test_validaciones_errores_claros_y_precio_negativo_o_cero():
    """
    Verifica mensajes claros en español cuando:
    - Mínimo > Probable o Probable > Máximo.
    - Se ingresan valores no numéricos.
    - El precio ofertado es cero o negativo.
    """
    partida_invalida = [
        {
            "categoria": "materiales",
            "descripcion": "Cable THHN mal ingresado",
            "unidad": "m",
            "cantidad": 100,
            "valor_min": 1500,
            "valor_prob": 900,
            "valor_max": 2000,
        }
    ]
    with pytest.raises(ErrorValidacionCotizacion) as exc_rango:
        simular_cotizacion(partida_invalida)
    assert "Rango inválido" in str(exc_rango.value)

    # Valor no numérico
    partida_no_num = [
        {
            "categoria": "materiales",
            "descripcion": "Cable con texto",
            "unidad": "m",
            "cantidad": "cien",
            "valor_min": 1000,
            "valor_prob": 1200,
            "valor_max": 1500,
        }
    ]
    with pytest.raises(ErrorValidacionCotizacion) as exc_num:
        simular_cotizacion(partida_no_num)
    assert "número válido" in str(exc_num.value)

    # Precio ofertado cero o negativo
    partidas_ok = obtener_plantilla_electrica()[:2]
    with pytest.raises(ErrorValidacionCotizacion) as exc_cero:
        simular_cotizacion(partidas_ok, precio_ofertado_usuario=0)
    assert "mayor que cero" in str(exc_cero.value)

    with pytest.raises(ErrorValidacionCotizacion) as exc_neg:
        simular_cotizacion(partidas_ok, precio_ofertado_usuario=-500000)
    assert "mayor que cero" in str(exc_neg.value)

    with pytest.raises(ErrorValidacionCotizacion) as exc_eval:
        evaluar_precio_puntual(-100, np.array([1000.0, 2000.0]), 1500.0)
    assert "mayor que cero" in str(exc_eval.value)


def test_carga_csv_competencia_historial_y_costos():
    """
    Verifica que los tres archivos CSV de ejemplo se generen y procesen correctamente.
    """
    rutas = asegurar_archivos_csv_ejemplo(costo_ref_clp=10537254.0, superficie_ref_m2=120.0)

    cal_comp = procesar_csv_calibracion(rutas["competencia"].read_bytes(), "competencia.csv")
    assert cal_comp["tipo"] == "competencia"
    assert cal_comp["n_registros"] == 40
    assert cal_comp["normalizado_m2"] is True
    assert cal_comp["filas_descartadas"] == 0

    cal_hist = procesar_csv_calibracion(rutas["historial"].read_bytes(), "historial.csv")
    assert cal_hist["tipo"] == "historial"
    assert cal_hist["n_registros"] == 30
    assert cal_hist["beta1"] < 0
    assert cal_hist["filas_descartadas"] == 0

    partidas_csv = procesar_csv_base_costos(rutas["base_costos"].read_bytes())
    assert len(partidas_csv) == 18
    assert partidas_csv.filas_descartadas == 0


def test_seed_fechas_relativas_bloqueo_plan_y_pdf():
    """
    Verifica que:
    1. El seed cree siempre 2 cotizaciones en el mes actual ('2 de 3 cotizaciones usadas este mes').
    2. Permita crear una tercera cotización en el mes (llegando a 3 de 3).
    3. Bloquee con HTTP 403 la creación de una cuarta cotización en el mes.
    4. Rechace con HTTP 400 un precio ofertado negativo o cero en la API.
    5. El endpoint /api/reset-demo restablezca el contador a 2 de 3.
    6. El generador de PDF produzca un documento PDF válido con encabezado %PDF.
    """
    from app import app

    client = app.test_client()

    r_reset = client.post("/api/reset-demo")
    assert r_reset.status_code == 200
    data_reset = r_reset.get_json()
    assert data_reset["ok"] is True
    assert data_reset["info_plan"]["usadas_mes"] == 2
    assert data_reset["info_plan"]["texto_contador"] == "2 de 3 cotizaciones usadas este mes"

    # Verificar que la API rechace precio ofertado <= 0 con error claro en español
    r_precio_neg = client.patch("/api/cotizaciones/1/precio", json={"precio_ofertado_clp": -1000})
    assert r_precio_neg.status_code == 400
    assert "mayor que cero" in r_precio_neg.get_json()["error"]

    # Crear la 3ra cotización del mes -> debe permitirse (3 de 3)
    payload_nueva = {
        "nombre": "Instalación eléctrica Bodega Test 3",
        "cliente": "Empresa Test SpA",
        "tipo_proyecto": "Instalación eléctrica comercial",
        "superficie_m2": 100,
        "puntos_electricos": 30,
        "ciudad": "Los Ángeles",
        "plazo_dias": 15,
        "partidas": obtener_plantilla_electrica()[:3],
    }
    r_tercera = client.post("/api/cotizaciones", json=payload_nueva)
    assert r_tercera.status_code == 200
    assert r_tercera.get_json()["info_plan"]["usadas_mes"] == 3

    # Intentar crear la 4ta cotización del mes -> debe bloquearse con 403
    r_cuarta = client.post("/api/cotizaciones", json=payload_nueva)
    assert r_cuarta.status_code == 403
    assert r_cuarta.get_json()["limite_alcanzado"] is True

    # Descargar PDF de la cotización principal (#1)
    r_pdf = client.get("/propuesta/1/pdf")
    assert r_pdf.status_code == 200
    assert r_pdf.data.startswith(b"%PDF")
    assert len(r_pdf.data) > 2000

    # Restablecer demo al finalizar la prueba para dejar 2 de 3
    r_reset_fin = client.post("/api/reset-demo")
    assert r_reset_fin.get_json()["info_plan"]["usadas_mes"] == 2


def test_todas_las_7_pantallas_y_descargas_csv():
    """
    Recorre todas las 7 pantallas HTML y los endpoints de descarga CSV para verificar
    que respondan HTTP 200, muestren la insignia 'Datos de demostración', el contador
    '2 de 3 cotizaciones usadas este mes' y el pie de página institucional.
    """
    from app import app

    client = app.test_client()
    client.post("/api/reset-demo")

    rutas_html = [
        "/",
        "/nueva",
        "/cotizacion/1/editar",
        "/resultados/1",
        "/historial",
        "/propuesta/1",
        "/planes",
        "/hoja-de-ruta",
    ]
    for ruta in rutas_html:
        resp = client.get(ruta)
        assert resp.status_code == 200, f"Fallo en ruta {ruta}"
        html = resp.data.decode("utf-8")
        assert "CotizaSmart - Proyecto TI II, Universidad de Concepción, Campus Los Ángeles" in html
        assert "Jorge Campos, Benjamin Muñoz, Raul Vergara" in html
        assert "2 de 3 cotizaciones usadas este mes" in html

    for ruta_demo in ["/", "/resultados/1", "/historial", "/propuesta/1"]:
        html_demo = client.get(ruta_demo).data.decode("utf-8")
        assert "Datos de demostración" in html_demo

    # Verificar correcciones menores: coma decimal en titular de Resultados y pluralización '1 obra'
    html_panel = client.get("/").data.decode("utf-8")
    assert "1 obra" in html_panel
    assert "1 obras" not in html_panel

    html_res1 = client.get("/resultados/1").data.decode("utf-8")
    assert "Con este precio hay 92,5% de probabilidad de ganar dinero (riesgo de pérdida bajo: 7,5%)." in html_res1
    assert "92.5%" not in html_res1

    html_roadmap = client.get("/hoja-de-ruta").data.decode("utf-8")
    assert "NO IMPLEMENTADO" in html_roadmap
    assert (
        "Plan Business con asistente de IA, integración con Mercado Público y base de costos regional"
        in html_roadmap
    )

    for tipo_csv in ["competencia", "historial", "base_costos"]:
        r_csv = client.get(f"/descargar-csv/{tipo_csv}")
        assert r_csv.status_code == 200
        assert len(r_csv.data) > 200


def test_pantalla_planes_tres_planes_business_deshabilitado_y_bloqueo():
    """
    Verifica los requisitos de la pantalla Planes y Hoja de Ruta:
    - /planes responde 200 y contiene los tres nombres de plan (Plan Gratis, Plan Pro, Plan Business).
    - Contiene la insignia 'PRÓXIMAMENTE' y 'Hasta 30 cotizaciones al mes'.
    - El botón del Plan Business está deshabilitado ('disabled') con texto 'Próximamente' y sin onclick.
    - No se usa la expresión 'IA entrenada'.
    - El bloqueo de la cuarta cotización del plan gratuito sigue funcionando (HTTP 403).
    """
    import re
    from app import app

    client = app.test_client()
    client.post("/api/reset-demo")

    resp = client.get("/planes")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")

    for nombre_plan in ("Plan Gratis", "Plan Pro", "Plan Business"):
        assert nombre_plan in html

    assert "PRÓXIMAMENTE" in html
    assert "Hasta 30 cotizaciones al mes" in html
    assert "Precio estimado, sujeto a validación" in html
    assert "Plan en desarrollo: no está disponible en esta versión de CotizaSmart" in html
    assert "IA entrenada" not in html

    # Verificar que el botón del Plan Business esté deshabilitado y sin acción onclick
    match_btn = re.search(
        r'<button[^>]*id="btn-plan-business"[^>]*>(.*?)</button>', html, re.DOTALL
    )
    assert match_btn is not None, "No se encontró el botón del Plan Business"
    tag_apertura = match_btn.group(0)
    texto_boton = match_btn.group(1).strip()
    assert "disabled" in tag_apertura
    assert "onclick" not in tag_apertura
    assert texto_boton == "Próximamente"

    # Confirmar que el bloqueo de la 4ta cotización sigue funcionando intacto
    payload_nueva = {
        "nombre": "Instalación eléctrica Test Planes",
        "cliente": "Cliente Test SpA",
        "tipo_proyecto": "Instalación eléctrica comercial",
        "superficie_m2": 120,
        "puntos_electricos": 40,
        "ciudad": "Los Ángeles",
        "plazo_dias": 15,
        "partidas": obtener_plantilla_electrica()[:2],
    }
    r_3 = client.post("/api/cotizaciones", json=payload_nueva)
    assert r_3.status_code == 200
    assert r_3.get_json()["info_plan"]["usadas_mes"] == 3

    r_4 = client.post("/api/cotizaciones", json=payload_nueva)
    assert r_4.status_code == 403
    assert r_4.get_json()["limite_alcanzado"] is True

    # Dejar restablecido en 2 de 3
    r_reset = client.post("/api/reset-demo")
    assert r_reset.get_json()["info_plan"]["usadas_mes"] == 2
