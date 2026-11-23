"""
Generador de datos de demostración (seed) y archivos CSV de ejemplo para CotizaSmart.
Trabajo 3 - Tecnología de la Información II, Universidad de Concepción (Campus Los Ángeles).
Autores: Jorge Campos, Benjamin Muñoz y Raul Vergara.
"""

from __future__ import annotations
from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Any

from modelos import db, Cotizacion, Partida, DatasetCalibracion
from motor_calculo import simular_cotizacion, procesar_csv_calibracion

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


def obtener_plantilla_electrica() -> list[dict[str, Any]]:
    """
    Retorna la plantilla de 18 partidas realistas para instalaciones eléctricas en CLP.
    Incluye marcas independientes 'sensible_cobre' (cables, tableros, protecciones, malla a tierra)
    y 'sensible_dolar' (luminarias LED, tableros y protecciones importadas).
    """
    return [
        # --- MATERIALES (12 partidas) ---
        {
            "orden": 1,
            "categoria": "materiales",
            "descripcion": "Cable THHN/THWN-2 12 AWG (3,31 mm²) circuitos de enchufes y fuerza",
            "unidad": "m",
            "cantidad": 480,
            "valor_min": 680,
            "valor_prob": 730,
            "valor_max": 1480,
            "merma_pct": 8.0,
            "valor_hora": 0.0,
            "sensible_cobre": True,
            "sensible_dolar": False,
        },
        {
            "orden": 2,
            "categoria": "materiales",
            "descripcion": "Cable THHN/THWN-2 14 AWG (2,08 mm²) circuitos de iluminación interior y vitrina",
            "unidad": "m",
            "cantidad": 360,
            "valor_min": 470,
            "valor_prob": 510,
            "valor_max": 1040,
            "merma_pct": 7.0,
            "valor_hora": 0.0,
            "sensible_cobre": True,
            "sensible_dolar": False,
        },
        {
            "orden": 3,
            "categoria": "materiales",
            "descripcion": "Cable EVA Libre de Halógenos 8 AWG (8,37 mm²) alimentador general empalme-tablero",
            "unidad": "m",
            "cantidad": 65,
            "valor_min": 2300,
            "valor_prob": 2500,
            "valor_max": 5100,
            "merma_pct": 6.0,
            "valor_hora": 0.0,
            "sensible_cobre": True,
            "sensible_dolar": False,
        },
        {
            "orden": 4,
            "categoria": "materiales",
            "descripcion": "Tablero general metálico embutido 36 módulos IP55 con barras colectoras de cobre",
            "unidad": "un",
            "cantidad": 2,
            "valor_min": 142000,
            "valor_prob": 155000,
            "valor_max": 310000,
            "merma_pct": 0.0,
            "valor_hora": 0.0,
            "sensible_cobre": True,
            "sensible_dolar": True,
        },
        {
            "orden": 5,
            "categoria": "materiales",
            "descripcion": "Interruptores termomagnéticos 1x10A, 1x16A y 3x40A curva C 10kA (protecciones importadas SEC)",
            "unidad": "un",
            "cantidad": 18,
            "valor_min": 8500,
            "valor_prob": 9200,
            "valor_max": 18200,
            "merma_pct": 3.0,
            "valor_hora": 0.0,
            "sensible_cobre": True,
            "sensible_dolar": True,
        },
        {
            "orden": 6,
            "categoria": "materiales",
            "descripcion": "Protectores diferenciales 2x25A y 4x40A sensibilidad 30mA clase A/AC (protecciones importadas)",
            "unidad": "un",
            "cantidad": 6,
            "valor_min": 33000,
            "valor_prob": 36000,
            "valor_max": 71000,
            "merma_pct": 2.0,
            "valor_hora": 0.0,
            "sensible_cobre": True,
            "sensible_dolar": True,
        },
        {
            "orden": 7,
            "categoria": "materiales",
            "descripcion": "Tubería conduit acero galvanizado EMT 20 mm y 25 mm con coplas y conectores",
            "unidad": "tira 3m",
            "cantidad": 85,
            "valor_min": 4800,
            "valor_prob": 5200,
            "valor_max": 10200,
            "merma_pct": 10.0,
            "valor_hora": 0.0,
            "sensible_cobre": False,
            "sensible_dolar": False,
        },
        {
            "orden": 8,
            "categoria": "materiales",
            "descripcion": "Bandeja portaconductores escalerilla galvanizada 150x50 mm con soportes trapecio",
            "unidad": "m",
            "cantidad": 28,
            "valor_min": 13200,
            "valor_prob": 14400,
            "valor_max": 28000,
            "merma_pct": 8.0,
            "valor_hora": 0.0,
            "sensible_cobre": False,
            "sensible_dolar": False,
        },
        {
            "orden": 9,
            "categoria": "materiales",
            "descripcion": "Enchufes dobles 10/16A más tierra alveolos protegidos línea comercial + cajas",
            "unidad": "pto",
            "cantidad": 32,
            "valor_min": 7600,
            "valor_prob": 8200,
            "valor_max": 15800,
            "merma_pct": 5.0,
            "valor_hora": 0.0,
            "sensible_cobre": False,
            "sensible_dolar": False,
        },
        {
            "orden": 10,
            "categoria": "materiales",
            "descripcion": "Paneles Luminarias LED 60x60 cm 40W 4000K + kits de emergencia autónomos importados",
            "unidad": "un",
            "cantidad": 24,
            "valor_min": 21500,
            "valor_prob": 23500,
            "valor_max": 45000,
            "merma_pct": 4.0,
            "valor_hora": 0.0,
            "sensible_cobre": False,
            "sensible_dolar": True,
        },
        {
            "orden": 11,
            "categoria": "materiales",
            "descripcion": "Malla puesta a tierra cable cobre desnudo 2 AWG + 3 barras Copperweld 5/8\" x 1,5m",
            "unidad": "gl",
            "cantidad": 1,
            "valor_min": 210000,
            "valor_prob": 230000,
            "valor_max": 485000,
            "merma_pct": 5.0,
            "valor_hora": 0.0,
            "sensible_cobre": True,
            "sensible_dolar": False,
        },
        {
            "orden": 12,
            "categoria": "materiales",
            "descripcion": "Cajas de derivación, prensacables, rieles DIN, borneras, ferretería y cintas 3M",
            "unidad": "gl",
            "cantidad": 1,
            "valor_min": 160000,
            "valor_prob": 175000,
            "valor_max": 340000,
            "merma_pct": 10.0,
            "valor_hora": 0.0,
            "sensible_cobre": False,
            "sensible_dolar": False,
        },
        # --- MANO DE OBRA (3 partidas) ---
        {
            "orden": 13,
            "categoria": "mano_obra",
            "descripcion": "Maestro electricista primera (montaje de tableros, cableado y conexionado)",
            "unidad": "HH",
            "cantidad": 1,
            "valor_min": 130,
            "valor_prob": 145,
            "valor_max": 310,
            "merma_pct": 0.0,
            "valor_hora": 11500.0,
            "sensible_cobre": False,
            "sensible_dolar": False,
        },
        {
            "orden": 14,
            "categoria": "mano_obra",
            "descripcion": "Ayudante eléctrico avanzado (canalización EMT, soportación y tendido)",
            "unidad": "HH",
            "cantidad": 1,
            "valor_min": 145,
            "valor_prob": 162,
            "valor_max": 345,
            "merma_pct": 0.0,
            "valor_hora": 7200.0,
            "sensible_cobre": False,
            "sensible_dolar": False,
        },
        {
            "orden": 15,
            "categoria": "mano_obra",
            "descripcion": "Ingeniero / Instalador autorizado SEC Clase A (planos As-Built y pruebas RIC)",
            "unidad": "HH",
            "cantidad": 1,
            "valor_min": 22,
            "valor_prob": 25,
            "valor_max": 55,
            "merma_pct": 0.0,
            "valor_hora": 18500.0,
            "sensible_cobre": False,
            "sensible_dolar": False,
        },
        # --- SUBCONTRATOS (2 partidas) ---
        {
            "orden": 16,
            "categoria": "subcontratos",
            "descripcion": "Medición geoeléctrica, protocolo de aislación y tramitación certificado TE1 SEC",
            "unidad": "gl",
            "cantidad": 1,
            "valor_min": 270000,
            "valor_prob": 295000,
            "valor_max": 580000,
            "merma_pct": 0.0,
            "valor_hora": 0.0,
            "sensible_cobre": False,
            "sensible_dolar": False,
        },
        {
            "orden": 17,
            "categoria": "subcontratos",
            "descripcion": "Arriendo de andamios modulados, ranuradora de hormigón y fletes a obra",
            "unidad": "gl",
            "cantidad": 1,
            "valor_min": 165000,
            "valor_prob": 180000,
            "valor_max": 370000,
            "merma_pct": 0.0,
            "valor_hora": 0.0,
            "sensible_cobre": False,
            "sensible_dolar": False,
        },
        # --- IMPREVISTOS (1 partida) ---
        {
            "orden": 18,
            "categoria": "imprevistos",
            "descripcion": "Contingencia por pasadas de losa ocultas, interferencias y observaciones SEC",
            "unidad": "%",
            "cantidad": 1,
            "valor_min": 3.0,
            "valor_prob": 5.0,
            "valor_max": 21.0,
            "merma_pct": 0.0,
            "valor_hora": 0.0,
            "sensible_cobre": False,
            "sensible_dolar": False,
        },
    ]


def asegurar_archivos_csv_ejemplo(
    costo_ref_clp: float = 10537254.0, superficie_ref_m2: float = 120.0
) -> dict[str, Path]:
    """
    Crea (o actualiza) los tres archivos CSV descargables de ejemplo en CotizaSmart/data/:
    1. precios_competencia_ejemplo.csv (40 filas con columna superficie_m2)
    2. historial_cotizaciones_ejemplo.csv (30 filas)
    3. base_costos_ejemplo.csv (plantilla de costos eléctricos con sensible_cobre y sensible_dolar)
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ahora = datetime.now()

    # 1. CSV de precios de competencia (40 filas con superficie_m2 para normalizar por tamaño)
    ruta_comp = DATA_DIR / "precios_competencia_ejemplo.csv"
    ciudades = [
        "Los Ángeles",
        "Concepción",
        "Chillán",
        "Temuco",
        "Talcahuano",
        "San Pedro de la Paz",
        "Mulchén",
        "Nacimiento",
        "Angol",
        "Coronel",
    ]
    superficies_m2 = [
        80, 95, 110, 120, 130, 145, 160, 100, 120, 180,
        90, 120, 150, 200, 115, 125, 140, 175, 120, 220,
        85, 105, 120, 135, 165, 190, 120, 155, 210, 240,
        100, 120, 140, 170, 195, 120, 130, 185, 250, 300,
    ]
    factores_comp = [
        1.04, 1.07, 1.09, 1.11, 1.12, 1.14, 1.15, 1.16, 1.17, 1.18,
        1.19, 1.20, 1.21, 1.22, 1.23, 1.24, 1.25, 1.26, 1.27, 1.27,
        1.28, 1.29, 1.30, 1.31, 1.32, 1.33, 1.34, 1.35, 1.36, 1.38,
        1.39, 1.41, 1.43, 1.45, 1.47, 1.49, 1.52, 1.55, 1.59, 1.64,
    ]
    costo_m2_ref = float(costo_ref_clp) / max(float(superficie_ref_m2), 1.0)
    lineas_comp = ["proyecto,rubro,superficie_m2,precio_adjudicado,region,fecha"]
    for i, factor in enumerate(factores_comp):
        ciudad = ciudades[i % len(ciudades)]
        sup_i = superficies_m2[i % len(superficies_m2)]
        region = (
            "La Araucanía"
            if ciudad in ("Temuco", "Angol")
            else ("Ñuble" if ciudad == "Chillán" else "Biobío")
        )
        precio_adj = int(round((costo_m2_ref * sup_i * factor) / 1000.0) * 1000)
        fecha_str = (ahora - timedelta(days=12 + i * 6)).strftime("%d-%m-%Y")
        nombre_proy = f"Habilitación Eléctrica Comercial #{i + 1:02d} ({sup_i} m²) - {ciudad}"
        lineas_comp.append(
            f"{nombre_proy},Instalación eléctrica comercial,{sup_i},{precio_adj},{region},{fecha_str}"
        )
    ruta_comp.write_text("\n".join(lineas_comp) + "\n", encoding="utf-8")

    # 2. CSV de historial de cotizaciones (30 filas: proyecto, costo_estimado, precio_ofertado, resultado)
    ruta_hist = DATA_DIR / "historial_cotizaciones_ejemplo.csv"
    casos_hist = [
        ("Local Farmacia Av. Alemania - Los Ángeles", 7800000, 1.12, 1),
        ("Oficinas Contables Centro - Concepción", 6400000, 1.14, 1),
        ("Minimarket Villa Galilea - Los Ángeles", 5200000, 1.15, 1),
        ("Panadería Artesanal - Mulchén", 8900000, 1.16, 1),
        ("Clínica Veterinaria - San Pedro de la Paz", 9400000, 1.18, 1),
        ("Bodega Agrícola Ruta 5 - Los Ángeles", 14200000, 1.19, 1),
        ("Centro Médico Dental - Chillán", 11100000, 1.20, 1),
        ("Showroom Automotriz - Concepción", 16500000, 1.21, 0),
        ("Cafetería Boulevard - Los Ángeles", 6900000, 1.22, 1),
        ("Ferretería Industrial - Cabrero", 12800000, 1.23, 1),
        ("Gimnasio Urbano 180 m² - Temuco", 10500000, 1.24, 1),
        ("Laboratorio Clínico - Los Ángeles", 9800000, 1.24, 0),
        ("Óptica y Consulta - Concepción", 5900000, 1.25, 1),
        ("Supermercado Vecinal - Nacimiento", 15400000, 1.26, 1),
        ("Restaurante Costanera - Talcahuano", 11900000, 1.26, 0),
        ("Tienda Electrónica Mall - Los Ángeles", 8400000, 1.27, 1),
        ("Taller Mecánico Multimarcas - Angol", 13100000, 1.28, 1),
        ("Sala de Ventas Inmobiliaria - Concepción", 7300000, 1.28, 1),
        ("Centro Estético Sor Vicenta - Los Ángeles", 6700000, 1.29, 1),
        ("Sucursal Caja de Compensación - Chillán", 14800000, 1.30, 1),
        ("Frigorífico Frutícola - Laja", 19200000, 1.31, 0),
        ("Notaría y Conservador - Los Ángeles", 8600000, 1.32, 1),
        ("Colegio Particular Subvencionado - Coronel", 17400000, 1.33, 1),
        ("Carnicería Cadena Regional - Temuco", 9100000, 1.34, 0),
        ("Cowork Corporativo - Concepción", 10900000, 1.36, 0),
        ("Centro Logístico - San Carlos", 21500000, 1.37, 0),
        ("Galería Comercial Colón - Los Ángeles", 12300000, 1.39, 0),
        ("Planta Envasadora - Mulchén", 18700000, 1.41, 0),
        ("Clínica Kinesiología - Concepción", 7600000, 1.44, 0),
        ("Pabellón Industrial Maderas - Los Ángeles", 23400000, 1.48, 0),
    ]
    lineas_hist = ["proyecto,costo_estimado,precio_ofertado,resultado"]
    for nombre_p, c_est, ratio_p, res in casos_hist:
        p_of = int(round((c_est * ratio_p) / 10000.0) * 10000)
        lineas_hist.append(f"{nombre_p},{c_est},{p_of},{res}")
    ruta_hist.write_text("\n".join(lineas_hist) + "\n", encoding="utf-8")

    # 3. Plantilla CSV de base de costos eléctricos
    ruta_costos = DATA_DIR / "base_costos_ejemplo.csv"
    lineas_costos = [
        "descripcion,unidad,precio_min,precio_probable,precio_max,categoria,cantidad,merma_pct,sensible_cobre,sensible_dolar"
    ]
    for p in obtener_plantilla_electrica():
        desc_limpia = p["descripcion"].replace(",", " -")
        lineas_costos.append(
            f"{desc_limpia},{p['unidad']},{int(p['valor_min'])},{int(p['valor_prob'])},"
            f"{int(p['valor_max'])},{p['categoria']},{p['cantidad']},{p['merma_pct']},"
            f"{'si' if p['sensible_cobre'] else 'no'},{'si' if p['sensible_dolar'] else 'no'}"
        )
    ruta_costos.write_text("\n".join(lineas_costos) + "\n", encoding="utf-8")

    return {
        "competencia": ruta_comp,
        "historial": ruta_hist,
        "base_costos": ruta_costos,
    }


def _crear_partidas_escaladas(escala: float) -> list[dict[str, Any]]:
    """
    Escala las cantidades de la plantilla eléctrica para generar cotizaciones históricas realistas.
    """
    base = obtener_plantilla_electrica()
    resultado = []
    for item in base:
        copia = dict(item)
        if copia["categoria"] != "imprevistos":
            nueva_cant = max(1.0, round(copia["cantidad"] * escala, 1))
            if copia["unidad"] in ("un", "pto", "gl", "tira 3m", "HH"):
                nueva_cant = float(max(1, int(round(nueva_cant))))
            copia["cantidad"] = nueva_cant
        resultado.append(copia)
    return resultado


def poblar_datos_demostracion(forzar_reinicio: bool = False) -> dict[str, Any]:
    """
    Carga los datos de demostración en SQLite si la base está vacía o si forzar_reinicio=True.
    Garantiza que las fechas sean relativas a la fecha actual de modo que SIEMPRE existan
    exactamente 2 cotizaciones en el mes actual ("2 de 3 cotizaciones usadas este mes").
    """
    if not forzar_reinicio and Cotizacion.query.count() > 0:
        asegurar_archivos_csv_ejemplo()
        return {"reiniciado": False, "total_cotizaciones": Cotizacion.query.count()}

    Partida.query.delete()
    Cotizacion.query.delete()
    DatasetCalibracion.query.delete()
    db.session.flush()

    ahora = datetime.now()
    inicio_mes_actual = ahora.replace(day=1, hour=9, minute=30, second=0, microsecond=0)
    fin_mes_anterior = inicio_mes_actual - timedelta(days=1)

    # 1. Simular la cotización estrella: "Instalación eléctrica local comercial 120 m² - Los Ángeles"
    partidas_demo = obtener_plantilla_electrica()
    sim_demo = simular_cotizacion(
        partidas=partidas_demo,
        var_cobre=0.0,
        var_dolar=0.0,
        sens_cobre=0.6,
        sens_dolar=0.3,
        gg_min=9.0,
        gg_prob=12.0,
        gg_max=22.0,
        utilidad_deseada=20.0,
        superficie_m2=120.0,
        n_simulaciones=10000,
        semilla=42,
        calibracion=None,
    )

    costo_ref = float(sim_demo["resumen"]["costo_esperado_clp"])
    rutas_csv = asegurar_archivos_csv_ejemplo(costo_ref_clp=costo_ref, superficie_ref_m2=120.0)

    # 2. Crear los 2 datasets de calibración de ejemplo en la base de datos
    datos_comp = procesar_csv_calibracion(
        rutas_csv["competencia"].read_bytes(), "precios_competencia_ejemplo.csv"
    )
    datos_comp["es_demo"] = True
    ds_comp = DatasetCalibracion(
        nombre="Precios adjudicados competencia Biobío/Sur (40 obras)",
        tipo="competencia",
        es_demo=True,
        activo=False,
        n_registros=datos_comp["n_registros"],
        fecha_carga=inicio_mes_actual,
        datos_json=json.dumps(datos_comp, ensure_ascii=False),
    )

    datos_hist = procesar_csv_calibracion(
        rutas_csv["historial"].read_bytes(), "historial_cotizaciones_ejemplo.csv"
    )
    datos_hist["es_demo"] = True
    ds_hist = DatasetCalibracion(
        nombre="Historial propio licitaciones eléctricas (30 cotizaciones)",
        tipo="historial",
        es_demo=True,
        activo=False,
        n_registros=datos_hist["n_registros"],
        fecha_carga=inicio_mes_actual,
        datos_json=json.dumps(datos_hist, ensure_ascii=False),
    )
    db.session.add_all([ds_comp, ds_hist])
    db.session.flush()

    # 3. Crear la cotización estrella (#1 del mes actual)
    res_demo = sim_demo["resumen"]
    ev_demo = sim_demo["evaluacion_ofertado"]

    cot_principal = Cotizacion(
        codigo=f"COT-{ahora.year}-010",
        nombre="Instalación eléctrica local comercial 120 m² - Los Ángeles",
        cliente="Comercializadora gastronómica y retail Biobío SpA",
        rut_cliente="76.548.320-4",
        tipo_proyecto="Instalación eléctrica comercial",
        superficie_m2=120.0,
        puntos_electricos=56,
        ciudad="Los Ángeles",
        plazo_dias=21,
        estado="enviada",
        es_demo=True,
        fecha_creacion=ahora,
        fecha_actualizacion=ahora,
        var_cobre=0.0,
        var_dolar=0.0,
        sens_cobre=0.6,
        sens_dolar=0.3,
        gg_min=9.0,
        gg_prob=12.0,
        gg_max=22.0,
        utilidad_deseada=20.0,
        semilla_simulacion=42,
        costo_esperado_clp=res_demo["costo_esperado_clp"],
        costo_p50_clp=res_demo["costo_p50_clp"],
        costo_p80_clp=res_demo["costo_p80_clp"],
        costo_p90_clp=res_demo["costo_p90_clp"],
        precio_min_seguro_clp=res_demo["precio_min_seguro_clp"],
        precio_optimo_clp=res_demo["precio_optimo_clp"],
        precio_ofertado_clp=ev_demo["precio_ofertado_clp"],
        prob_perdida_pct=ev_demo["prob_perdida_pct"],
        prob_ganar_pct=ev_demo["prob_ganar_licitacion_pct"],
        ganancia_esperada_clp=ev_demo["ganancia_esperada_clp"],
        margen_esperado_pct=ev_demo["margen_esperado_pct"],
        resultados_json=json.dumps(sim_demo, ensure_ascii=False),
    )
    db.session.add(cot_principal)
    db.session.flush()

    for p_dict in partidas_demo:
        db.session.add(Partida(cotizacion_id=cot_principal.id, **p_dict))

    # 4. Crear 9 cotizaciones adicionales (1 más en el mes actual = 2 de 3; 8 en meses anteriores)
    specs_historicas = [
        {
            "codigo": f"COT-{ahora.year}-009",
            "nombre": "Habilitación eléctrica Clínica Dental Almagro 85 m² - Los Ángeles",
            "cliente": "Centro Odontológico Almagro Ltda.",
            "rut_cliente": "77.112.450-9",
            "tipo": "Instalación eléctrica comercial",
            "m2": 85.0,
            "puntos": 38,
            "ciudad": "Los Ángeles",
            "plazo": 15,
            "estado": "borrador",
            "fecha": inicio_mes_actual + timedelta(hours=2),
            "escala": 0.72,
            "factor_precio": 1.24,
            "var_cobre": 4.0,
            "var_dolar": 2.0,
            "semilla": 109,
        },
        {
            "codigo": f"COT-{ahora.year}-008",
            "nombre": "Normalización tableros y alimentadores Bodega Agroindustrial - Mulchén",
            "cliente": "Agroindustrial del Sur S.A.",
            "rut_cliente": "96.845.110-2",
            "tipo": "Instalación eléctrica industrial",
            "m2": 320.0,
            "puntos": 92,
            "ciudad": "Mulchén",
            "plazo": 35,
            "estado": "ganada",
            "fecha": fin_mes_anterior - timedelta(days=3),
            "escala": 1.65,
            "factor_precio": 1.27,
            "var_cobre": 0.0,
            "var_dolar": 0.0,
            "semilla": 108,
        },
        {
            "codigo": f"COT-{ahora.year}-007",
            "nombre": "Instalación eléctrica integral Vivienda Unifamiliar 140 m² - Concepción",
            "cliente": "Inmobiliaria y Constructora Andalué SpA",
            "rut_cliente": "76.209.880-1",
            "tipo": "Instalación eléctrica residencial",
            "m2": 140.0,
            "puntos": 64,
            "ciudad": "Concepción",
            "plazo": 25,
            "estado": "ganada",
            "fecha": fin_mes_anterior - timedelta(days=14),
            "escala": 0.90,
            "factor_precio": 1.26,
            "var_cobre": -2.0,
            "var_dolar": 0.0,
            "semilla": 107,
        },
        {
            "codigo": f"COT-{ahora.year}-006",
            "nombre": "Remodelación iluminación LED y fuerza Supermercado Vecinal - Nacimiento",
            "cliente": "Supermercados Cordillera Ltda.",
            "rut_cliente": "78.431.900-K",
            "tipo": "Instalación eléctrica comercial",
            "m2": 210.0,
            "puntos": 78,
            "ciudad": "Nacimiento",
            "plazo": 28,
            "estado": "perdida",
            "fecha": fin_mes_anterior - timedelta(days=27),
            "escala": 1.28,
            "factor_precio": 1.37,
            "var_cobre": 6.0,
            "var_dolar": 3.0,
            "semilla": 106,
        },
        {
            "codigo": f"COT-{ahora.year}-005",
            "nombre": "Empalme trifásico y malla a tierra Taller Metalmecánico - Chillán",
            "cliente": "Maestranza Ñuble SpA",
            "rut_cliente": "76.990.312-7",
            "tipo": "Instalación eléctrica industrial",
            "m2": 260.0,
            "puntos": 54,
            "ciudad": "Chillán",
            "plazo": 24,
            "estado": "ganada",
            "fecha": fin_mes_anterior - timedelta(days=41),
            "escala": 1.35,
            "factor_precio": 1.16,
            "var_cobre": 8.0,
            "var_dolar": 4.0,
            "semilla": 105,
        },
        {
            "codigo": f"COT-{ahora.year}-004",
            "nombre": "Instalación eléctrica Cafetería y Cowork Av. Alemania - Los Ángeles",
            "cliente": "Gastronomía Santa María SpA",
            "rut_cliente": "77.540.128-3",
            "tipo": "Instalación eléctrica comercial",
            "m2": 95.0,
            "puntos": 42,
            "ciudad": "Los Ángeles",
            "plazo": 18,
            "estado": "ganada",
            "fecha": fin_mes_anterior - timedelta(days=56),
            "escala": 0.82,
            "factor_precio": 1.27,
            "var_cobre": 0.0,
            "var_dolar": 0.0,
            "semilla": 104,
        },
        {
            "codigo": f"COT-{ahora.year}-003",
            "nombre": "Recableado y certificación TE1 Condominio Los Robles - San Pedro de la Paz",
            "cliente": "Comunidad Edificio Los Robles",
            "rut_cliente": "56.102.440-8",
            "tipo": "Instalación eléctrica residencial",
            "m2": 180.0,
            "puntos": 70,
            "ciudad": "San Pedro de la Paz",
            "plazo": 22,
            "estado": "perdida",
            "fecha": fin_mes_anterior - timedelta(days=74),
            "escala": 1.10,
            "factor_precio": 1.35,
            "var_cobre": 0.0,
            "var_dolar": 0.0,
            "semilla": 103,
        },
        {
            "codigo": f"COT-{ahora.year}-002",
            "nombre": "Circuito de respaldo UPS y tableros computacionales Notaría - Los Ángeles",
            "cliente": "Segunda Notaría de Los Ángeles",
            "rut_cliente": "70.412.800-5",
            "tipo": "Instalación eléctrica comercial",
            "m2": 110.0,
            "puntos": 48,
            "ciudad": "Los Ángeles",
            "plazo": 14,
            "estado": "enviada",
            "fecha": fin_mes_anterior - timedelta(days=92),
            "escala": 0.88,
            "factor_precio": 1.21,
            "var_cobre": 3.0,
            "var_dolar": 1.0,
            "semilla": 102,
        },
        {
            "codigo": f"COT-{ahora.year}-001",
            "nombre": "Planta de packing frutícola línea de selección - Angol",
            "cliente": "Exportadora Malleco Fruits S.A.",
            "rut_cliente": "96.512.740-6",
            "tipo": "Instalación eléctrica industrial",
            "m2": 450.0,
            "puntos": 120,
            "ciudad": "Angol",
            "plazo": 45,
            "estado": "ganada",
            "fecha": fin_mes_anterior - timedelta(days=115),
            "escala": 2.05,
            "factor_precio": 1.28,
            "var_cobre": 0.0,
            "var_dolar": 0.0,
            "semilla": 101,
        },
    ]

    for spec in specs_historicas:
        partidas_h = _crear_partidas_escaladas(spec["escala"])
        sim_base = simular_cotizacion(
            partidas=partidas_h,
            var_cobre=spec["var_cobre"],
            var_dolar=spec["var_dolar"],
            sens_cobre=0.6,
            sens_dolar=0.3,
            gg_min=9.0,
            gg_prob=12.0,
            gg_max=22.0,
            utilidad_deseada=20.0,
            superficie_m2=spec["m2"],
            n_simulaciones=10000,
            semilla=spec["semilla"],
        )
        precio_of = round(sim_base["resumen"]["costo_esperado_clp"] * spec["factor_precio"])
        sim_h = simular_cotizacion(
            partidas=partidas_h,
            var_cobre=spec["var_cobre"],
            var_dolar=spec["var_dolar"],
            sens_cobre=0.6,
            sens_dolar=0.3,
            gg_min=9.0,
            gg_prob=12.0,
            gg_max=22.0,
            utilidad_deseada=20.0,
            superficie_m2=spec["m2"],
            n_simulaciones=10000,
            semilla=spec["semilla"],
            precio_ofertado_usuario=precio_of,
        )
        res_h = sim_h["resumen"]
        ev_h = sim_h["evaluacion_ofertado"]

        cot_h = Cotizacion(
            codigo=spec["codigo"],
            nombre=spec["nombre"],
            cliente=spec["cliente"],
            rut_cliente=spec["rut_cliente"],
            tipo_proyecto=spec["tipo"],
            superficie_m2=spec["m2"],
            puntos_electricos=spec["puntos"],
            ciudad=spec["ciudad"],
            plazo_dias=spec["plazo"],
            estado=spec["estado"],
            es_demo=True,
            fecha_creacion=spec["fecha"],
            fecha_actualizacion=spec["fecha"],
            var_cobre=spec["var_cobre"],
            var_dolar=spec["var_dolar"],
            sens_cobre=0.6,
            sens_dolar=0.3,
            gg_min=9.0,
            gg_prob=12.0,
            gg_max=22.0,
            utilidad_deseada=20.0,
            semilla_simulacion=spec["semilla"],
            costo_esperado_clp=res_h["costo_esperado_clp"],
            costo_p50_clp=res_h["costo_p50_clp"],
            costo_p80_clp=res_h["costo_p80_clp"],
            costo_p90_clp=res_h["costo_p90_clp"],
            precio_min_seguro_clp=res_h["precio_min_seguro_clp"],
            precio_optimo_clp=res_h["precio_optimo_clp"],
            precio_ofertado_clp=ev_h["precio_ofertado_clp"],
            prob_perdida_pct=ev_h["prob_perdida_pct"],
            prob_ganar_pct=ev_h["prob_ganar_licitacion_pct"],
            ganancia_esperada_clp=ev_h["ganancia_esperada_clp"],
            margen_esperado_pct=ev_h["margen_esperado_pct"],
            resultados_json=json.dumps(sim_h, ensure_ascii=False),
        )
        db.session.add(cot_h)
        db.session.flush()
        for p_dict in partidas_h:
            db.session.add(Partida(cotizacion_id=cot_h.id, **p_dict))

    db.session.commit()
    return {
        "reiniciado": True,
        "total_cotizaciones": Cotizacion.query.count(),
        "cotizacion_principal_id": cot_principal.id,
    }
