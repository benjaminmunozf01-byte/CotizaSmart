"""
Modelos de base de datos SQLite con SQLAlchemy para CotizaSmart.
Trabajo 3 - Tecnología de la Información II, Universidad de Concepción (Campus Los Ángeles).
Autores: Jorge Campos, Benjamin Muñoz y Raul Vergara.
"""

from datetime import datetime
import json
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class DatasetCalibracion(db.Model):
    """
    Almacena un conjunto de datos de calibración de probabilidad de ganar P(win | precio),
    ya sea desde precios adjudicados de la competencia o desde historial propio (ganada/perdida).
    """
    __tablename__ = "datasets_calibracion"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(160), nullable=False)
    tipo = db.Column(db.String(40), nullable=False)  # 'competencia' | 'historial'
    es_demo = db.Column(db.Boolean, default=False, nullable=False)
    activo = db.Column(db.Boolean, default=False, nullable=False)
    n_registros = db.Column(db.Integer, default=0, nullable=False)
    fecha_carga = db.Column(db.DateTime, default=datetime.now, nullable=False)
    datos_json = db.Column(db.Text, nullable=False, default="{}")

    def obtener_datos(self) -> dict:
        """Retorna el diccionario con los datos y parámetros ajustados del dataset."""
        try:
            return json.loads(self.datos_json or "{}")
        except (TypeError, ValueError):
            return {}

    def to_dict(self) -> dict:
        """Serializa el dataset de calibración para respuestas JSON."""
        return {
            "id": self.id,
            "nombre": self.nombre,
            "tipo": self.tipo,
            "es_demo": self.es_demo,
            "activo": self.activo,
            "n_registros": self.n_registros,
            "fecha_carga": self.fecha_carga.strftime("%d-%m-%Y %H:%M"),
            "datos": self.obtener_datos(),
        }


class Cotizacion(db.Model):
    """
    Modelo principal de una cotización de obra eléctrica con simulación Montecarlo.
    """
    __tablename__ = "cotizaciones"

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(32), nullable=False, index=True)
    nombre = db.Column(db.String(200), nullable=False)
    cliente = db.Column(db.String(160), nullable=False)
    rut_cliente = db.Column(db.String(25), nullable=True, default="76.482.910-K")
    tipo_proyecto = db.Column(
        db.String(80), nullable=False, default="Instalación eléctrica comercial"
    )
    superficie_m2 = db.Column(db.Float, nullable=False, default=120.0)
    puntos_electricos = db.Column(db.Integer, nullable=False, default=45)
    ciudad = db.Column(db.String(100), nullable=False, default="Los Ángeles")
    plazo_dias = db.Column(db.Integer, nullable=False, default=20)

    # Estado comercial: 'borrador', 'enviada', 'ganada', 'perdida'
    estado = db.Column(db.String(30), nullable=False, default="borrador")
    es_demo = db.Column(db.Boolean, default=False, nullable=False)

    fecha_creacion = db.Column(db.DateTime, default=datetime.now, nullable=False)
    fecha_actualizacion = db.Column(
        db.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )

    # Parámetros de escenario de mercado (Cobre y Dólar)
    var_cobre = db.Column(db.Float, nullable=False, default=0.0)   # -20% a +30%
    var_dolar = db.Column(db.Float, nullable=False, default=0.0)   # -10% a +15%
    sens_cobre = db.Column(db.Float, nullable=False, default=0.6)  # Factor por defecto 0,6
    sens_dolar = db.Column(db.Float, nullable=False, default=0.3)  # Factor por defecto 0,3

    # Costos indirectos (Gastos Generales en % sobre costo directo) y utilidad referencial
    gg_min = db.Column(db.Float, nullable=False, default=8.0)
    gg_prob = db.Column(db.Float, nullable=False, default=11.0)
    gg_max = db.Column(db.Float, nullable=False, default=16.0)
    utilidad_deseada = db.Column(db.Float, nullable=False, default=20.0)
    semilla_simulacion = db.Column(db.Integer, nullable=True, default=42)

    # Referencia opcional a calibración específica
    calibracion_id = db.Column(
        db.Integer, db.ForeignKey("datasets_calibracion.id"), nullable=True
    )

    # Campos para la propuesta comercial PDF
    alcance_propuesta = db.Column(
        db.Text,
        nullable=True,
        default=(
            "Suministro, canalización, cableado, montaje de tableros, protecciones "
            "termomagnéticas y diferenciales, instalación de luminarias LED, enchufes, "
            "malla de puesta a tierra, pruebas de aislación y tramitación de "
            "certificación TE1 ante la Superintendencia de Electricidad y Combustibles (SEC) "
            "según normativa RIC vigente."
        ),
    )
    validez_dias = db.Column(db.Integer, nullable=False, default=15)
    condiciones_pago = db.Column(
        db.String(300),
        nullable=False,
        default="50% anticipo contra orden de compra, 50% contra recepción conforme y entrega de certificado TE1 SEC.",
    )

    # Métricas resumen de la última simulación (en CLP y %)
    costo_esperado_clp = db.Column(db.Float, nullable=False, default=0.0)
    costo_p50_clp = db.Column(db.Float, nullable=False, default=0.0)
    costo_p80_clp = db.Column(db.Float, nullable=False, default=0.0)
    costo_p90_clp = db.Column(db.Float, nullable=False, default=0.0)
    precio_min_seguro_clp = db.Column(db.Float, nullable=False, default=0.0)
    precio_optimo_clp = db.Column(db.Float, nullable=False, default=0.0)
    precio_ofertado_clp = db.Column(db.Float, nullable=False, default=0.0)

    prob_perdida_pct = db.Column(db.Float, nullable=False, default=0.0)
    prob_ganar_pct = db.Column(db.Float, nullable=False, default=0.0)
    ganancia_esperada_clp = db.Column(db.Float, nullable=False, default=0.0)
    margen_esperado_pct = db.Column(db.Float, nullable=False, default=0.0)

    # Resultados completos serializados en JSON para carga rápida
    resultados_json = db.Column(db.Text, nullable=True)

    # Relación con partidas ordenadas
    partidas = db.relationship(
        "Partida",
        backref="cotizacion",
        cascade="all, delete-orphan",
        order_by="Partida.orden",
        lazy=True,
    )

    def semaforo(self) -> str:
        """
        Retorna el color del semáforo según la probabilidad de pérdida:
        - 'verde': < 10%
        - 'amarillo': 10% a 25%
        - 'rojo': > 25%
        """
        if self.prob_perdida_pct < 10.0:
            return "verde"
        if self.prob_perdida_pct <= 25.0:
            return "amarillo"
        return "rojo"

    def obtener_resultados(self) -> dict:
        """Deserializa el JSON de resultados de simulación si existe."""
        if not self.resultados_json:
            return {}
        try:
            return json.loads(self.resultados_json)
        except (TypeError, ValueError):
            return {}

    def to_dict(self, incluir_partidas: bool = True, incluir_resultados: bool = False) -> dict:
        """Serializa la cotización a diccionario para el frontend o API."""
        data = {
            "id": self.id,
            "codigo": self.codigo,
            "nombre": self.nombre,
            "cliente": self.cliente,
            "rut_cliente": self.rut_cliente or "76.482.910-K",
            "tipo_proyecto": self.tipo_proyecto,
            "superficie_m2": self.superficie_m2,
            "puntos_electricos": self.puntos_electricos,
            "ciudad": self.ciudad,
            "plazo_dias": self.plazo_dias,
            "estado": self.estado,
            "es_demo": self.es_demo,
            "fecha_creacion": self.fecha_creacion.strftime("%d-%m-%Y"),
            "fecha_iso": self.fecha_creacion.strftime("%Y-%m-%d"),
            "var_cobre": self.var_cobre,
            "var_dolar": self.var_dolar,
            "sens_cobre": self.sens_cobre,
            "sens_dolar": self.sens_dolar,
            "gg_min": self.gg_min,
            "gg_prob": self.gg_prob,
            "gg_max": self.gg_max,
            "utilidad_deseada": self.utilidad_deseada,
            "semilla_simulacion": self.semilla_simulacion,
            "calibracion_id": self.calibracion_id,
            "alcance_propuesta": self.alcance_propuesta,
            "validez_dias": self.validez_dias,
            "condiciones_pago": self.condiciones_pago,
            "costo_esperado_clp": round(self.costo_esperado_clp),
            "costo_p50_clp": round(self.costo_p50_clp),
            "costo_p80_clp": round(self.costo_p80_clp),
            "costo_p90_clp": round(self.costo_p90_clp),
            "precio_min_seguro_clp": round(self.precio_min_seguro_clp),
            "precio_optimo_clp": round(self.precio_optimo_clp),
            "precio_ofertado_clp": round(self.precio_ofertado_clp),
            "prob_perdida_pct": round(self.prob_perdida_pct, 1),
            "prob_ganar_pct": round(self.prob_ganar_pct, 1),
            "ganancia_esperada_clp": round(self.ganancia_esperada_clp),
            "margen_esperado_pct": round(self.margen_esperado_pct, 1),
            "semaforo": self.semaforo(),
        }
        if incluir_partidas:
            data["partidas"] = [p.to_dict() for p in self.partidas]
        if incluir_resultados:
            data["resultados"] = self.obtener_resultados()
        return data


class Partida(db.Model):
    """
    Partida de costo asociada a una cotización.
    Categorías soportadas: 'materiales', 'mano_obra', 'subcontratos', 'imprevistos'.
    - En 'materiales': valor_min/prob/max = precio unitario CLP; merma_pct = % de merma.
    - En 'mano_obra': valor_min/prob/max = horas-hombre (HH); valor_hora = tarifa CLP/HH; cantidad = cuadrillas o factor (usualmente 1).
    - En 'subcontratos': valor_min/prob/max = precio unitario CLP; cantidad = unidades.
    - En 'imprevistos': valor_min/prob/max = % sobre el costo directo base.
    """
    __tablename__ = "partidas"

    id = db.Column(db.Integer, primary_key=True)
    cotizacion_id = db.Column(
        db.Integer, db.ForeignKey("cotizaciones.id", ondelete="CASCADE"), nullable=False
    )
    orden = db.Column(db.Integer, nullable=False, default=0)
    categoria = db.Column(db.String(40), nullable=False, default="materiales")
    descripcion = db.Column(db.String(240), nullable=False)
    unidad = db.Column(db.String(30), nullable=False, default="un")
    cantidad = db.Column(db.Float, nullable=False, default=1.0)

    valor_min = db.Column(db.Float, nullable=False, default=0.0)
    valor_prob = db.Column(db.Float, nullable=False, default=0.0)
    valor_max = db.Column(db.Float, nullable=False, default=0.0)

    merma_pct = db.Column(db.Float, nullable=False, default=0.0)     # Solo materiales
    valor_hora = db.Column(db.Float, nullable=False, default=0.0)    # Solo mano_obra
    sensible_cobre = db.Column(db.Boolean, nullable=False, default=False)
    sensible_dolar = db.Column(db.Boolean, nullable=False, default=False)

    def to_dict(self) -> dict:
        """Serializa la partida para uso en el frontend y en el motor de cálculo."""
        return {
            "id": self.id,
            "orden": self.orden,
            "categoria": self.categoria,
            "descripcion": self.descripcion,
            "unidad": self.unidad,
            "cantidad": self.cantidad,
            "valor_min": self.valor_min,
            "valor_prob": self.valor_prob,
            "valor_max": self.valor_max,
            "merma_pct": self.merma_pct,
            "valor_hora": self.valor_hora,
            "sensible_cobre": bool(self.sensible_cobre),
            "sensible_dolar": bool(self.sensible_dolar),
        }
