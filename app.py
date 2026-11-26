"""
Aplicación principal Flask para CotizaSmart — Cotizador de obras con riesgo medido (Montecarlo).
Trabajo 3 - Tecnología de la Información II, Universidad de Concepción (Campus Los Ángeles).
Autores: Jorge Campos, Benjamin Muñoz y Raul Vergara.
"""

from __future__ import annotations
from datetime import datetime
import io
import json
import os
from pathlib import Path
from typing import Any

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
import numpy as np
from sqlalchemy import inspect

from modelos import db, Cotizacion, Partida, DatasetCalibracion
from motor_calculo import (
    ErrorValidacionCotizacion,
    calcular_probabilidad_ganar,
    convertir_numero_obligatorio,
    procesar_csv_base_costos,
    procesar_csv_calibracion,
    simular_cotizacion,
)
from pdf_generator import (
    calcular_desglose_comercial_cliente,
    formatear_clp,
    generar_pdf_propuesta,
)
from seed import (
    DATA_DIR,
    asegurar_archivos_csv_ejemplo,
    obtener_plantilla_electrica,
    poblar_datos_demostracion,
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "cotizasmart.db"

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "cotizasmart-udec-la-2026")

db.init_app(app)


# --- FILTROS JINJA2 EN FORMATO CHILENO ---

@app.template_filter("clp")
def filtro_clp(valor: Any) -> str:
    """Formatea montos en CLP con punto de miles y sin decimales ($1.250.000)."""
    try:
        return formatear_clp(float(valor or 0))
    except (TypeError, ValueError):
        return "$0"


@app.template_filter("pct")
def filtro_pct(valor: Any) -> str:
    """Formatea porcentajes con 1 decimal y coma chilena (14,5%)."""
    try:
        num = float(valor or 0.0)
        return f"{num:.1f}%".replace(".", ",")
    except (TypeError, ValueError):
        return "0,0%"


@app.template_filter("dec_cl")
def filtro_dec_cl(valor: Any, decimales: int = 1) -> str:
    """Formatea un número decimal con coma chilena."""
    try:
        num = float(valor or 0.0)
        return f"{num:.{decimales}f}".replace(".", ",")
    except (TypeError, ValueError):
        return "0"


# --- FUNCIONES AUXILIARES DE NEGOCIO ---

LIMITE_PLAN_GRATIS = 3


def obtener_estado_plan() -> dict[str, Any]:
    """
    Calcula cuántas cotizaciones se han creado en el mes calendario actual
    y determina si el plan gratuito (3 cotizaciones/mes) está disponible o bloqueado.
    """
    ahora = datetime.now()
    inicio_mes = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    usadas_mes = Cotizacion.query.filter(Cotizacion.fecha_creacion >= inicio_mes).count()
    bloqueado = usadas_mes >= LIMITE_PLAN_GRATIS
    restantes = max(0, LIMITE_PLAN_GRATIS - usadas_mes)
    porcentaje = min(100, int(round((usadas_mes / LIMITE_PLAN_GRATIS) * 100)))

    return {
        "plan_nombre": "Plan Gratuito",
        "usadas_mes": usadas_mes,
        "limite_mes": LIMITE_PLAN_GRATIS,
        "restantes": restantes,
        "bloqueado": bloqueado,
        "porcentaje_uso": porcentaje,
        "texto_contador": f"{usadas_mes} de {LIMITE_PLAN_GRATIS} cotizaciones usadas este mes",
    }


def obtener_calibracion_activa(
    calibracion_id: int | None = None,
) -> tuple[dict[str, Any] | None, DatasetCalibracion | None]:
    """
    Retorna los datos de calibración solicitados por ID o el dataset activo globalmente.
    """
    ds = None
    if calibracion_id:
        ds = db.session.get(DatasetCalibracion, int(calibracion_id))
    if ds is None:
        ds = (
            DatasetCalibracion.query.filter_by(activo=True)
            .order_by(DatasetCalibracion.id.desc())
            .first()
        )
    if ds is None:
        return None, None
    datos = ds.obtener_datos()
    datos["id"] = ds.id
    datos["nombre"] = ds.nombre
    datos["es_demo"] = ds.es_demo
    return datos, ds


def asegurar_resultados_cotizacion(cot: Cotizacion) -> dict[str, Any]:
    """
    Retorna el diccionario de resultados de una cotización; si no está en caché,
    ejecuta la simulación Montecarlo y la persiste. Normaliza porcentajes con coma decimal.
    """
    res = cot.obtener_resultados()
    if res and "resumen" in res and "curva_precio_optimo" in res:
        for clave_ev in ("evaluacion_ofertado", "evaluacion_optimo", "evaluacion_ingenuo"):
            ev_obj = res.get(clave_ev)
            if isinstance(ev_obj, dict) and isinstance(ev_obj.get("mensaje_semaforo"), str):
                import re
                ev_obj["mensaje_semaforo"] = re.sub(
                    r"(\d+)\.(\d+)%", r"\1,\2%", ev_obj["mensaje_semaforo"]
                )
        return res

    cal_dict, _ = obtener_calibracion_activa(cot.calibracion_id)
    partidas_list = [p.to_dict() for p in cot.partidas] or obtener_plantilla_electrica()
    res = simular_cotizacion(
        partidas=partidas_list,
        var_cobre=cot.var_cobre,
        var_dolar=cot.var_dolar,
        sens_cobre=cot.sens_cobre,
        sens_dolar=cot.sens_dolar,
        gg_min=cot.gg_min,
        gg_prob=cot.gg_prob,
        gg_max=cot.gg_max,
        utilidad_deseada=cot.utilidad_deseada,
        superficie_m2=cot.superficie_m2,
        semilla=cot.semilla_simulacion or 42,
        calibracion=cal_dict,
        precio_ofertado_usuario=cot.precio_ofertado_clp if cot.precio_ofertado_clp > 0 else None,
    )
    cot.resultados_json = json.dumps(res, ensure_ascii=False)
    db.session.commit()
    return res


@app.context_processor
def inyectar_contexto_global() -> dict[str, Any]:
    """Inyecta en todas las plantillas el contador del plan gratuito y la cotización demo principal."""
    try:
        info_plan = obtener_estado_plan()
        cot_demo = (
            Cotizacion.query.filter(Cotizacion.nombre.ilike("%120 m²%"))
            .order_by(Cotizacion.id.asc())
            .first()
        )
        if not cot_demo:
            cot_demo = Cotizacion.query.order_by(Cotizacion.fecha_creacion.desc()).first()
        return {
            "info_plan": info_plan,
            "cot_demo_id": cot_demo.id if cot_demo else 1,
            "anio_actual": datetime.now().year,
        }
    except Exception:
        return {
            "info_plan": {
                "usadas_mes": 2,
                "limite_mes": 3,
                "restantes": 1,
                "bloqueado": False,
                "porcentaje_uso": 67,
                "texto_contador": "2 de 3 cotizaciones usadas este mes",
            },
            "cot_demo_id": 1,
            "anio_actual": 2026,
        }


# --- RUTAS DE PANTALLAS (7 VISTAS PRINCIPALES) ---

@app.route("/favicon.ico")
def favicon():
    """Sirve el favicon vectorial SVG con el rayo en gradiente morado (#7C3AED a #A78BFA)."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        '<defs><linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">'
        '<stop offset="0%" stop-color="#7C3AED"/><stop offset="100%" stop-color="#A78BFA"/>'
        '</linearGradient></defs>'
        '<rect width="32" height="32" rx="8" fill="url(#g)"/>'
        '<polygon points="18,4 8,18 15,18 13,28 24,14 17,14" fill="#1E1033"/>'
        '</svg>'
    )
    return app.response_class(svg, mimetype="image/svg+xml")


@app.route("/")
def panel_inicio():
    """Pantalla 1: Panel de inicio con KPIs, gráfico por estado, lista reciente y contador del plan."""
    cotizaciones = Cotizacion.query.order_by(Cotizacion.fecha_creacion.desc()).all()
    info_plan = obtener_estado_plan()

    total = len(cotizaciones)
    margen_promedio = (
        float(np.mean([c.margen_esperado_pct for c in cotizaciones])) if total > 0 else 0.0
    )
    riesgo_promedio = (
        float(np.mean([c.prob_perdida_pct for c in cotizaciones])) if total > 0 else 0.0
    )

    ganadas = sum(1 for c in cotizaciones if c.estado == "ganada")
    perdidas = sum(1 for c in cotizaciones if c.estado == "perdida")
    cerradas = ganadas + perdidas
    tasa_ganadas = (ganadas / cerradas * 100.0) if cerradas > 0 else 0.0

    conteo_estados = {
        "borrador": sum(1 for c in cotizaciones if c.estado == "borrador"),
        "enviada": sum(1 for c in cotizaciones if c.estado == "enviada"),
        "ganada": ganadas,
        "perdida": perdidas,
    }

    tiene_datos_demo = any(c.es_demo for c in cotizaciones)

    kpis = {
        "cotizaciones_mes": info_plan["usadas_mes"],
        "total_historico": total,
        "margen_esperado_promedio": round(margen_promedio, 1),
        "tasa_ganadas": round(tasa_ganadas, 1),
        "ganadas_count": ganadas,
        "cerradas_count": cerradas,
        "riesgo_promedio": round(riesgo_promedio, 1),
    }

    return render_template(
        "panel.html",
        pagina_activa="panel",
        kpis=kpis,
        conteo_estados=conteo_estados,
        cotizaciones_recientes=[c.to_dict(incluir_partidas=False) for c in cotizaciones[:7]],
        tiene_datos_demo=tiene_datos_demo,
    )


@app.route("/nueva")
def nueva_cotizacion():
    """Pantalla 2: Asistente de 4 pasos para crear una nueva cotización."""
    datasets = DatasetCalibracion.query.order_by(DatasetCalibracion.id.desc()).all()
    _, ds_activo = obtener_calibracion_activa()
    return render_template(
        "nueva_cotizacion.html",
        pagina_activa="nueva",
        modo_edicion=False,
        cotizacion_editar=None,
        plantilla_inicial=obtener_plantilla_electrica(),
        datasets_calibracion=[d.to_dict() for d in datasets],
        calibracion_activa_id=ds_activo.id if ds_activo else None,
    )


@app.route("/cotizacion/<int:cot_id>/editar")
def editar_cotizacion(cot_id: int):
    """Pantalla 2 (modo edición): Abre una cotización existente en el asistente de 4 pasos."""
    cot = db.get_or_404(Cotizacion, cot_id)
    datasets = DatasetCalibracion.query.order_by(DatasetCalibracion.id.desc()).all()
    return render_template(
        "nueva_cotizacion.html",
        pagina_activa="nueva",
        modo_edicion=True,
        cotizacion_editar=cot.to_dict(incluir_partidas=True),
        plantilla_inicial=obtener_plantilla_electrica(),
        datasets_calibracion=[d.to_dict() for d in datasets],
        calibracion_activa_id=cot.calibracion_id,
    )


@app.route("/resultados/<int:cot_id>")
def ver_resultados(cot_id: int):
    """Pantalla 3: Pantalla estrella de resultados Montecarlo, curva de precio óptimo y tornado."""
    cot = db.get_or_404(Cotizacion, cot_id)
    resultados = asegurar_resultados_cotizacion(cot)
    datasets = DatasetCalibracion.query.order_by(DatasetCalibracion.id.desc()).all()
    todas_cotizaciones = Cotizacion.query.order_by(Cotizacion.fecha_creacion.desc()).all()

    return render_template(
        "resultados.html",
        pagina_activa="resultados",
        cotizacion=cot.to_dict(incluir_partidas=True),
        resultados=resultados,
        datasets_calibracion=[d.to_dict() for d in datasets],
        lista_cotizaciones=[c.to_dict(incluir_partidas=False) for c in todas_cotizaciones],
    )


@app.route("/historial")
def historial_calibracion():
    """Pantalla 4: Historial de cotizaciones guardadas y calibración con CSV."""
    cotizaciones = Cotizacion.query.order_by(Cotizacion.fecha_creacion.desc()).all()
    datasets = DatasetCalibracion.query.order_by(DatasetCalibracion.id.desc()).all()
    cal_dict, ds_activo = obtener_calibracion_activa()

    cot_ref = Cotizacion.query.order_by(Cotizacion.id.asc()).first()
    costo_ref = cot_ref.costo_esperado_clp if cot_ref and cot_ref.costo_esperado_clp > 0 else 10537254.0
    sup_ref = cot_ref.superficie_m2 if cot_ref and cot_ref.superficie_m2 > 0 else 120.0
    grilla_p = np.linspace(costo_ref * 0.90, costo_ref * 1.75, 60)

    curva_generica = calcular_probabilidad_ganar(grilla_p, costo_ref, None, superficie_m2=sup_ref) * 100.0
    curva_activa = calcular_probabilidad_ganar(grilla_p, costo_ref, cal_dict, superficie_m2=sup_ref) * 100.0

    curvas_datasets = {}
    for d in datasets:
        d_datos = d.obtener_datos()
        c_pts = calcular_probabilidad_ganar(grilla_p, costo_ref, d_datos, superficie_m2=sup_ref) * 100.0
        curvas_datasets[d.id] = [round(float(x), 1) for x in c_pts]

    datos_grafico_calibracion = {
        "costo_referencia_clp": round(costo_ref),
        "superficie_referencia_m2": round(sup_ref, 1),
        "precios_clp": [round(float(p)) for p in grilla_p],
        "ratios": [round(float(p / costo_ref), 2) for p in grilla_p],
        "curva_generica_pct": [round(float(x), 1) for x in curva_generica],
        "curva_activa_pct": [round(float(x), 1) for x in curva_activa],
        "curvas_por_dataset": curvas_datasets,
        "dataset_activo": ds_activo.to_dict() if ds_activo else None,
    }

    tiene_datos_demo = any(c.es_demo for c in cotizaciones) or any(d.es_demo for d in datasets)

    return render_template(
        "historial.html",
        pagina_activa="historial",
        cotizaciones=[c.to_dict(incluir_partidas=False) for c in cotizaciones],
        datasets=[d.to_dict() for d in datasets],
        dataset_activo=ds_activo.to_dict() if ds_activo else None,
        datos_grafico_calibracion=datos_grafico_calibracion,
        tiene_datos_demo=tiene_datos_demo,
    )


@app.route("/propuesta")
@app.route("/propuesta/<int:cot_id>")
def propuesta_comercial(cot_id: int | None = None):
    """Pantalla 5: Vista previa ejecutiva de la propuesta comercial y descarga PDF."""
    todas = Cotizacion.query.order_by(Cotizacion.fecha_creacion.desc()).all()
    if not todas:
        return redirect(url_for("nueva_cotizacion"))

    if cot_id is None:
        cot_demo = Cotizacion.query.filter(Cotizacion.nombre.ilike("%120 m²%")).first()
        cot = cot_demo or todas[0]
    else:
        cot = db.get_or_404(Cotizacion, cot_id)

    cot_dict = cot.to_dict(incluir_partidas=True)
    desglose = calcular_desglose_comercial_cliente(cot_dict)

    return render_template(
        "propuesta.html",
        pagina_activa="propuesta",
        cotizacion=cot_dict,
        desglose=desglose,
        lista_cotizaciones=[c.to_dict(incluir_partidas=False) for c in todas],
    )


@app.route("/planes")
def planes_precios():
    """Pantalla 6: Comparativa de planes Gratis vs Pro ($49.000 CLP/mes)."""
    return render_template("planes.html", pagina_activa="planes")


@app.route("/hoja-de-ruta")
def hoja_de_ruta():
    """Pantalla 7: Línea de tiempo visual con 3 etapas (Hoy, Fase 2 y Fase 3)."""
    return render_template("hoja_ruta.html", pagina_activa="hoja_ruta")


# --- ENDPOINTS API REST JSON ---

@app.route("/api/plantilla-electrica", methods=["GET"])
def api_plantilla_electrica():
    """Retorna la plantilla de 18 partidas eléctricas típicas en CLP."""
    return jsonify({"ok": True, "partidas": obtener_plantilla_electrica()})


@app.route("/api/cargar-base-costos", methods=["POST"])
def api_cargar_base_costos():
    """
    Procesa un archivo CSV de base de costos, descarta filas vacías o no numéricas
    e informa cuántas filas fueron descartadas.
    """
    if "archivo" not in request.files:
        return jsonify({"ok": False, "error": "Debe adjuntar un archivo CSV."}), 400
    archivo = request.files["archivo"]
    try:
        partidas = procesar_csv_base_costos(archivo.read())
        descartadas = getattr(partidas, "filas_descartadas", 0)
        aviso_desc = (
            f" Se descartaron {descartadas} filas con celdas vacías o no numéricas."
            if descartadas > 0
            else " (0 filas descartadas)."
        )
        return jsonify(
            {
                "ok": True,
                "mensaje": f"Se cargaron {len(partidas)} partidas desde '{archivo.filename}'.{aviso_desc}",
                "filas_descartadas": descartadas,
                "partidas": list(partidas),
            }
        )
    except ErrorValidacionCotizacion as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Error al procesar CSV: {exc}"}), 400


@app.route("/api/simular", methods=["POST"])
def api_simular():
    """
    Endpoint del motor de cálculo Montecarlo (responde en < 0,2 segundos).
    Permite simular sin guardar o recalcular escenarios en vivo (cobre/dólar/calibración).
    """
    payload = request.get_json(silent=True) or {}
    try:
        partidas = payload.get("partidas") or []
        cal_id = payload.get("calibracion_id")
        cal_inline = payload.get("calibracion_datos")

        if cal_inline and isinstance(cal_inline, dict):
            cal_dict = cal_inline
        elif cal_id is not None and str(cal_id) != "0":
            cal_dict, _ = obtener_calibracion_activa(int(cal_id))
        elif str(cal_id) == "0":
            cal_dict = None
        else:
            cal_dict, _ = obtener_calibracion_activa()

        precio_usr = payload.get("precio_ofertado_clp")
        precio_usr_val = (
            precio_usr
            if ("precio_ofertado_clp" in payload and precio_usr not in (None, ""))
            else None
        )

        resultados = simular_cotizacion(
            partidas=partidas,
            var_cobre=payload.get("var_cobre", 0.0),
            var_dolar=payload.get("var_dolar", 0.0),
            sens_cobre=payload.get("sens_cobre", 0.6),
            sens_dolar=payload.get("sens_dolar", 0.3),
            gg_min=payload.get("gg_min", 9.0),
            gg_prob=payload.get("gg_prob", 12.0),
            gg_max=payload.get("gg_max", 22.0),
            utilidad_deseada=payload.get("utilidad_deseada", 20.0),
            superficie_m2=payload.get("superficie_m2", 120.0),
            n_simulaciones=10000,
            semilla=int(payload.get("semilla", 42) or 42),
            calibracion=cal_dict,
            precio_ofertado_usuario=precio_usr_val,
        )
        return jsonify({"ok": True, "resultados": resultados})
    except ErrorValidacionCotizacion as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Error en simulación: {exc}"}), 400


@app.route("/api/cotizaciones", methods=["POST"])
def api_guardar_cotizacion():
    """
    Crea una nueva cotización o actualiza una existente luego de ejecutar el motor Montecarlo.
    Verifica el límite del Plan Gratuito (3 cotizaciones por mes) al crear una nueva.
    """
    payload = request.get_json(silent=True) or {}
    cot_id = payload.get("id")

    try:
        es_edicion = bool(cot_id)
        if es_edicion:
            cot = db.get_or_404(Cotizacion, int(cot_id))
        else:
            info_plan = obtener_estado_plan()
            if info_plan["bloqueado"]:
                return (
                    jsonify(
                        {
                            "ok": False,
                            "limite_alcanzado": True,
                            "error": (
                                "Has alcanzado el límite de 3 cotizaciones mensuales del Plan Gratuito. "
                                "Actualiza al Plan Pro ($49.000 CLP/mes) para crear cotizaciones ilimitadas."
                            ),
                            "info_plan": info_plan,
                        }
                    ),
                    403,
                )
            ahora = datetime.now()
            consecutivo = Cotizacion.query.count() + 1
            cot = Cotizacion(
                codigo=f"COT-{ahora.year}-{consecutivo:03d}",
                fecha_creacion=ahora,
                es_demo=False,
            )

        partidas_raw = payload.get("partidas") or []
        cal_id = payload.get("calibracion_id")
        if cal_id in ("", "0", 0, None):
            cal_dict = None
            cot.calibracion_id = None
        else:
            cot.calibracion_id = int(cal_id)
            cal_dict, _ = obtener_calibracion_activa(cot.calibracion_id)

        var_cobre = convertir_numero_obligatorio(
            payload.get("var_cobre", 0.0), "Variación del cobre (%)"
        )
        var_dolar = convertir_numero_obligatorio(
            payload.get("var_dolar", 0.0), "Variación del dólar (%)"
        )
        sens_cobre = convertir_numero_obligatorio(
            payload.get("sens_cobre", 0.6), "Sensibilidad al cobre"
        )
        sens_dolar = convertir_numero_obligatorio(
            payload.get("sens_dolar", 0.3), "Sensibilidad al dólar"
        )
        gg_min = convertir_numero_obligatorio(
            payload.get("gg_min", 9.0), "Gastos generales mínimo (%)"
        )
        gg_prob = convertir_numero_obligatorio(
            payload.get("gg_prob", 12.0), "Gastos generales probable (%)"
        )
        gg_max = convertir_numero_obligatorio(
            payload.get("gg_max", 22.0), "Gastos generales máximo (%)"
        )
        utilidad_deseada = convertir_numero_obligatorio(
            payload.get("utilidad_deseada", 20.0), "Utilidad deseada (%)"
        )
        superficie_m2 = convertir_numero_obligatorio(
            payload.get("superficie_m2", 120.0), "Superficie (m²)"
        )
        if superficie_m2 <= 0:
            raise ErrorValidacionCotizacion("La superficie en m² debe ser mayor que cero.")

        puntos_el = convertir_numero_obligatorio(
            payload.get("puntos_electricos", 40), "Puntos eléctricos"
        )
        plazo_d = convertir_numero_obligatorio(
            payload.get("plazo_dias", 20), "Plazo de ejecución (días)"
        )
        semilla = int(payload.get("semilla_simulacion", 42) or 42)

        precio_usr = payload.get("precio_ofertado_clp")
        precio_usr_val = (
            precio_usr
            if ("precio_ofertado_clp" in payload and precio_usr not in (None, ""))
            else None
        )

        resultados = simular_cotizacion(
            partidas=partidas_raw,
            var_cobre=var_cobre,
            var_dolar=var_dolar,
            sens_cobre=sens_cobre,
            sens_dolar=sens_dolar,
            gg_min=gg_min,
            gg_prob=gg_prob,
            gg_max=gg_max,
            utilidad_deseada=utilidad_deseada,
            superficie_m2=superficie_m2,
            n_simulaciones=10000,
            semilla=semilla,
            calibracion=cal_dict,
            precio_ofertado_usuario=precio_usr_val,
        )

        cot.nombre = str(payload.get("nombre") or "Instalación eléctrica comercial").strip()
        cot.cliente = str(payload.get("cliente") or "Cliente Comercial SpA").strip()
        cot.rut_cliente = str(payload.get("rut_cliente") or "76.482.910-K").strip()
        cot.tipo_proyecto = str(
            payload.get("tipo_proyecto") or "Instalación eléctrica comercial"
        ).strip()
        cot.superficie_m2 = superficie_m2
        cot.puntos_electricos = max(1, int(round(puntos_el)))
        cot.ciudad = str(payload.get("ciudad") or "Los Ángeles").strip()
        cot.plazo_dias = max(1, int(round(plazo_d)))
        if payload.get("estado") in ("borrador", "enviada", "ganada", "perdida"):
            cot.estado = payload["estado"]

        cot.var_cobre = var_cobre
        cot.var_dolar = var_dolar
        cot.sens_cobre = sens_cobre
        cot.sens_dolar = sens_dolar
        cot.gg_min = gg_min
        cot.gg_prob = gg_prob
        cot.gg_max = gg_max
        cot.utilidad_deseada = utilidad_deseada
        cot.semilla_simulacion = semilla

        res = resultados["resumen"]
        ev = resultados["evaluacion_ofertado"]
        cot.costo_esperado_clp = res["costo_esperado_clp"]
        cot.costo_p50_clp = res["costo_p50_clp"]
        cot.costo_p80_clp = res["costo_p80_clp"]
        cot.costo_p90_clp = res["costo_p90_clp"]
        cot.precio_min_seguro_clp = res["precio_min_seguro_clp"]
        cot.precio_optimo_clp = res["precio_optimo_clp"]
        cot.precio_ofertado_clp = ev["precio_ofertado_clp"]
        cot.prob_perdida_pct = ev["prob_perdida_pct"]
        cot.prob_ganar_pct = ev["prob_ganar_licitacion_pct"]
        cot.ganancia_esperada_clp = ev["ganancia_esperada_clp"]
        cot.margen_esperado_pct = ev["margen_esperado_pct"]
        cot.resultados_json = json.dumps(resultados, ensure_ascii=False)

        if not es_edicion:
            db.session.add(cot)
            db.session.flush()
        else:
            Partida.query.filter_by(cotizacion_id=cot.id).delete()

        for idx, p in enumerate(partidas_raw):
            db.session.add(
                Partida(
                    cotizacion_id=cot.id,
                    orden=idx + 1,
                    categoria=str(p.get("categoria", "materiales")).lower(),
                    descripcion=str(p.get("descripcion", f"Partida #{idx + 1}")).strip(),
                    unidad=str(p.get("unidad", "un")).strip(),
                    cantidad=convertir_numero_obligatorio(p.get("cantidad", 1.0), "Cantidad"),
                    valor_min=convertir_numero_obligatorio(p.get("valor_min", 0.0), "Valor mínimo"),
                    valor_prob=convertir_numero_obligatorio(p.get("valor_prob", 0.0), "Valor probable"),
                    valor_max=convertir_numero_obligatorio(p.get("valor_max", 0.0), "Valor máximo"),
                    merma_pct=float(p.get("merma_pct", 0.0) or 0.0),
                    valor_hora=float(p.get("valor_hora", 0.0) or 0.0),
                    sensible_cobre=bool(p.get("sensible_cobre", False)),
                    sensible_dolar=bool(p.get("sensible_dolar", False)),
                )
            )

        db.session.commit()
        return jsonify(
            {
                "ok": True,
                "cotizacion_id": cot.id,
                "redirect_url": url_for("ver_resultados", cot_id=cot.id),
                "info_plan": obtener_estado_plan(),
            }
        )
    except ErrorValidacionCotizacion as exc:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        db.session.rollback()
        return jsonify({"ok": False, "error": f"No se pudo guardar la cotización: {exc}"}), 400


@app.route("/api/cotizaciones/<int:cot_id>/precio", methods=["PATCH"])
def api_actualizar_precio_y_escenario(cot_id: int):
    """
    Guarda el precio ofertado elegido en el slider de Resultados (y opcionalmente
    ajustes de cobre, dólar o calibración) en la cotización actual.
    """
    cot = db.get_or_404(Cotizacion, cot_id)
    payload = request.get_json(silent=True) or {}

    try:
        if "var_cobre" in payload:
            cot.var_cobre = convertir_numero_obligatorio(
                payload["var_cobre"], "Variación del cobre (%)"
            )
        if "var_dolar" in payload:
            cot.var_dolar = convertir_numero_obligatorio(
                payload["var_dolar"], "Variación del dólar (%)"
            )
        if "calibracion_id" in payload:
            c_id = payload["calibracion_id"]
            cot.calibracion_id = None if c_id in (None, "", 0, "0") else int(c_id)

        precio_val = None
        if "precio_ofertado_clp" in payload and payload["precio_ofertado_clp"] not in (None, ""):
            precio_val = convertir_numero_obligatorio(
                payload["precio_ofertado_clp"], "Precio ofertado"
            )
            if precio_val <= 0:
                raise ErrorValidacionCotizacion(
                    "El precio ofertado debe ser mayor que cero (no puede ser negativo ni cero)."
                )

        cal_dict, _ = obtener_calibracion_activa(cot.calibracion_id)
        partidas_list = [p.to_dict() for p in cot.partidas]
        resultados = simular_cotizacion(
            partidas=partidas_list,
            var_cobre=cot.var_cobre,
            var_dolar=cot.var_dolar,
            sens_cobre=cot.sens_cobre,
            sens_dolar=cot.sens_dolar,
            gg_min=cot.gg_min,
            gg_prob=cot.gg_prob,
            gg_max=cot.gg_max,
            utilidad_deseada=cot.utilidad_deseada,
            superficie_m2=cot.superficie_m2,
            semilla=cot.semilla_simulacion or 42,
            calibracion=cal_dict,
            precio_ofertado_usuario=precio_val,
        )

        res = resultados["resumen"]
        ev = resultados["evaluacion_ofertado"]
        cot.costo_esperado_clp = res["costo_esperado_clp"]
        cot.costo_p50_clp = res["costo_p50_clp"]
        cot.costo_p80_clp = res["costo_p80_clp"]
        cot.costo_p90_clp = res["costo_p90_clp"]
        cot.precio_min_seguro_clp = res["precio_min_seguro_clp"]
        cot.precio_optimo_clp = res["precio_optimo_clp"]
        cot.precio_ofertado_clp = ev["precio_ofertado_clp"]
        cot.prob_perdida_pct = ev["prob_perdida_pct"]
        cot.prob_ganar_pct = ev["prob_ganar_licitacion_pct"]
        cot.ganancia_esperada_clp = ev["ganancia_esperada_clp"]
        cot.margen_esperado_pct = ev["margen_esperado_pct"]
        cot.resultados_json = json.dumps(resultados, ensure_ascii=False)

        db.session.commit()
        return jsonify(
            {
                "ok": True,
                "mensaje": "Cotización actualizada correctamente.",
                "cotizacion": cot.to_dict(incluir_partidas=False),
                "resultados": resultados,
            }
        )
    except ErrorValidacionCotizacion as exc:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.route("/api/cotizaciones/<int:cot_id>/estado", methods=["PATCH"])
def api_cambiar_estado_cotizacion(cot_id: int):
    """Cambia el estado comercial de una cotización (borrador, enviada, ganada, perdida)."""
    cot = db.get_or_404(Cotizacion, cot_id)
    payload = request.get_json(silent=True) or {}
    nuevo_estado = str(payload.get("estado", "")).strip().lower()
    if nuevo_estado not in ("borrador", "enviada", "ganada", "perdida"):
        return jsonify({"ok": False, "error": "Estado inválido."}), 400

    cot.estado = nuevo_estado
    db.session.commit()
    return jsonify({"ok": True, "id": cot.id, "estado": cot.estado})


@app.route("/api/cotizaciones/<int:cot_id>/propuesta", methods=["PATCH"])
def api_actualizar_propuesta(cot_id: int):
    """Actualiza los textos comerciales de la propuesta antes de exportar el PDF."""
    cot = db.get_or_404(Cotizacion, cot_id)
    payload = request.get_json(silent=True) or {}

    try:
        if "cliente" in payload and str(payload["cliente"]).strip():
            cot.cliente = str(payload["cliente"]).strip()
        if "rut_cliente" in payload and str(payload["rut_cliente"]).strip():
            cot.rut_cliente = str(payload["rut_cliente"]).strip()
        if "alcance_propuesta" in payload:
            cot.alcance_propuesta = str(payload["alcance_propuesta"]).strip()
        if "validez_dias" in payload:
            val_d = convertir_numero_obligatorio(
                payload["validez_dias"], "Validez de la oferta (días)"
            )
            cot.validez_dias = max(1, int(round(val_d)))
        if "condiciones_pago" in payload:
            cot.condiciones_pago = str(payload["condiciones_pago"]).strip()

        db.session.commit()
        return jsonify({"ok": True, "cotizacion": cot.to_dict(incluir_partidas=False)})
    except ErrorValidacionCotizacion as exc:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.route("/api/calibracion/cargar", methods=["POST"])
def api_cargar_csv_calibracion():
    """
    Recibe un archivo CSV de precios de competencia o de historial de cotizaciones,
    calibra la curva P(win | precio), informa cuántas filas se descartaron y lo activa.
    """
    if "archivo" not in request.files:
        return jsonify({"ok": False, "error": "Debe seleccionar un archivo CSV."}), 400

    archivo = request.files["archivo"]
    nombre_usr = request.form.get("nombre", "").strip() or archivo.filename or "Dataset CSV"

    try:
        contenido = archivo.read()
        datos_cal = procesar_csv_calibracion(contenido, archivo.filename or "datos.csv")
        datos_cal["es_demo"] = False

        DatasetCalibracion.query.update({DatasetCalibracion.activo: False})
        nuevo_ds = DatasetCalibracion(
            nombre=nombre_usr,
            tipo=datos_cal["tipo"],
            es_demo=False,
            activo=True,
            n_registros=datos_cal["n_registros"],
            fecha_carga=datetime.now(),
            datos_json=json.dumps(datos_cal, ensure_ascii=False),
        )
        db.session.add(nuevo_ds)
        db.session.commit()

        cot_id = request.form.get("cotizacion_id")
        if cot_id and str(cot_id).isdigit():
            cot = db.session.get(Cotizacion, int(cot_id))
            if cot:
                cot.calibracion_id = nuevo_ds.id
                db.session.commit()

        descartadas = int(datos_cal.get("filas_descartadas", 0))
        aviso_tamano = datos_cal.get("aviso_tamano")
        msg = f"Calibración exitosa: {datos_cal['descripcion_metodo']}."
        if aviso_tamano:
            msg += f" Aviso: {aviso_tamano}."

        return jsonify(
            {
                "ok": True,
                "mensaje": msg,
                "filas_descartadas": descartadas,
                "aviso_tamano": aviso_tamano,
                "dataset": nuevo_ds.to_dict(),
            }
        )
    except ErrorValidacionCotizacion as exc:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        db.session.rollback()
        return jsonify({"ok": False, "error": f"Error al calibrar CSV: {exc}"}), 400


@app.route("/api/calibracion/<int:cal_id>/activar", methods=["POST"])
def api_activar_calibracion(cal_id: int):
    """
    Activa un dataset de calibración guardado (o vuelve a la curva genérica si cal_id == 0).
    """
    DatasetCalibracion.query.update({DatasetCalibracion.activo: False})
    ds_activo = None
    if cal_id > 0:
        ds_activo = db.get_or_404(DatasetCalibracion, cal_id)
        ds_activo.activo = True
    db.session.commit()
    return jsonify(
        {
            "ok": True,
            "activo_id": ds_activo.id if ds_activo else 0,
            "dataset": ds_activo.to_dict() if ds_activo else None,
        }
    )


@app.route("/api/reset-demo", methods=["POST"])
def api_reset_demo():
    """
    Restablece la base de datos al estado inicial de demostración
    ("2 de 3 cotizaciones usadas este mes").
    """
    info = poblar_datos_demostracion(forzar_reinicio=True)
    return jsonify(
        {
            "ok": True,
            "mensaje": "Datos de demostración restablecidos (2 de 3 cotizaciones usadas este mes).",
            "detalle": info,
            "info_plan": obtener_estado_plan(),
        }
    )


# --- DESCARGA DE PDF Y ARCHIVOS CSV DE EJEMPLO ---

@app.route("/propuesta/<int:cot_id>/pdf", methods=["GET"])
def descargar_pdf_propuesta(cot_id: int):
    """Genera y descarga el PDF profesional de la propuesta comercial."""
    cot = db.get_or_404(Cotizacion, cot_id)
    pdf_bytes = generar_pdf_propuesta(cot.to_dict(incluir_partidas=True))
    nombre_archivo = f"Propuesta_{cot.codigo}_{cot.ciudad.replace(' ', '_')}.pdf"
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=nombre_archivo,
    )


@app.route("/descargar-csv/<tipo>", methods=["GET"])
def descargar_csv_ejemplo(tipo: str):
    """Permite descargar cualquiera de los 3 archivos CSV de ejemplo."""
    rutas = asegurar_archivos_csv_ejemplo()
    mapa = {
        "competencia": (rutas["competencia"], "precios_competencia_ejemplo.csv"),
        "historial": (rutas["historial"], "historial_cotizaciones_ejemplo.csv"),
        "base_costos": (rutas["base_costos"], "base_costos_ejemplo.csv"),
    }
    if tipo not in mapa:
        return jsonify({"ok": False, "error": "Tipo de CSV no disponible."}), 404

    ruta_archivo, nombre_descarga = mapa[tipo]
    return send_file(
        ruta_archivo,
        mimetype="text/csv",
        as_attachment=True,
        download_name=nombre_descarga,
    )


def inicializar_base_datos() -> None:
    """Crea las tablas SQLite y carga el seed automáticamente si la base está vacía o desactualizada."""
    with app.app_context():
        inspector = inspect(db.engine)
        if inspector.has_table("partidas"):
            cols_partidas = {c["name"] for c in inspector.get_columns("partidas")}
            if "sensible_dolar" not in cols_partidas:
                db.drop_all()
        db.create_all()
        poblar_datos_demostracion(forzar_reinicio=False)


# Inicializar al importar el módulo (para gunicorn en Render/Railway y para python app.py)
inicializar_base_datos()


if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    print(f"Iniciando CotizaSmart en http://127.0.0.1:{puerto} ...")
    app.run(host="0.0.0.0", port=puerto, debug=debug_mode)
