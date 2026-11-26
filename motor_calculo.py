"""
Motor de simulación Montecarlo PERT vectorizado y optimización de precio ofertado para CotizaSmart.
Trabajo 3 - Tecnología de la Información II, Universidad de Concepción (Campus Los Ángeles).
Autores: Jorge Campos, Benjamin Muñoz y Raul Vergara.
"""

from __future__ import annotations
import io
import re
import time
from typing import Any
import numpy as np
import pandas as pd


class ErrorValidacionCotizacion(ValueError):
    """Excepción de negocio con mensaje claro en español para el usuario."""


class ListaPartidasCSV(list):
    """
    Subclase de list que conserva compatibilidad como lista de partidas
    y expone además el conteo de filas descartadas al leer un CSV.
    """

    def __init__(self, iterable=(), filas_descartadas: int = 0, total_filas: int = 0):
        super().__init__(iterable)
        self.filas_descartadas = int(filas_descartadas)
        self.total_filas = int(total_filas)


def limpiar_numero_chileno(valor_raw: Any) -> float | None:
    """
    Limpia y convierte un valor numérico en formato chileno o internacional sin borrar
    puntos a ciegas.
    Acepta:
      - "12500000"      -> 12500000.0
      - "12.500.000"    -> 12500000.0
      - "$12.500.000"   -> 12500000.0
      - "12500000.50"   -> 12500000.5
      - "12.500.000,50" -> 12500000.5
    Retorna None si la celda está vacía o no representa un número válido.
    """
    if valor_raw is None:
        return None
    if isinstance(valor_raw, (int, float, np.number)) and not isinstance(valor_raw, bool):
        val_f = float(valor_raw)
        if np.isnan(val_f) or np.isinf(val_f):
            return None
        return val_f

    s = str(valor_raw).strip()
    if not s or s.lower() in ("nan", "none", "null", "n/a", "-"):
        return None

    # Quitar símbolos de moneda ($ o CLP) y espacios exteriores
    s = re.sub(r"(?i)clp", "", s)
    s = s.replace("$", "").strip()
    if not s:
        return None

    # Rechazar si contiene espacios internos o caracteres ajenos a números
    if not re.match(r"^[\+\-]?\d[\d\.,]*$", s):
        return None

    tiene_punto = "." in s
    tiene_coma = "," in s

    if tiene_punto and tiene_coma:
        ultimo_punto = s.rfind(".")
        ultima_coma = s.rfind(",")
        if ultima_coma > ultimo_punto:
            # Formato chileno con miles '.' y decimal ',' -> ej: "12.500.000,50"
            parte_entera = s[:ultima_coma]
            parte_decimal = s[ultima_coma + 1 :]
            if "," in parte_entera or not re.match(r"^[\+\-]?\d{1,3}(\.\d{3})+$", parte_entera):
                return None
            s_norm = parte_entera.replace(".", "") + "." + parte_decimal
        else:
            # Formato anglosajón con miles ',' y decimal '.' -> ej: "12,500,000.50"
            parte_entera = s[:ultimo_punto]
            parte_decimal = s[ultimo_punto + 1 :]
            if "." in parte_entera or not re.match(r"^[\+\-]?\d{1,3}(,\d{3})+$", parte_entera):
                return None
            s_norm = parte_entera.replace(",", "") + "." + parte_decimal
    elif tiene_coma:
        # Solo comas: si hay 1 coma es separador decimal chileno ("12500000,50" o "5,5")
        if s.count(",") == 1:
            s_norm = s.replace(",", ".")
        elif re.match(r"^[\+\-]?\d{1,3}(,\d{3})+$", s):
            s_norm = s.replace(",", "")
        else:
            return None
    elif tiene_punto:
        n_puntos = s.count(".")
        if n_puntos > 1:
            # Múltiples puntos: deben ser separadores de miles exactos de 3 dígitos ("12.500.000")
            if not re.match(r"^[\+\-]?\d{1,3}(\.\d{3})+$", s):
                return None
            s_norm = s.replace(".", "")
        else:
            # Un único punto: distinguir entre decimal ("12500000.50", "9.5", "0.600")
            # y miles con un solo punto ("142.000", "12.500")
            partes = s.split(".")
            prefijo = partes[0].lstrip("+-")
            sufijo = partes[1]
            if (
                len(sufijo) == 3
                and 1 <= len(prefijo) <= 3
                and not prefijo.startswith("0")
            ):
                # Ejemplo: "142.000" o "12.500" -> separador de miles chileno
                s_norm = s.replace(".", "")
            else:
                # Ejemplo: "12500000.50" o "12.5" o "0.600" -> punto decimal
                s_norm = s
    else:
        s_norm = s

    try:
        num = float(s_norm)
    except ValueError:
        return None

    if np.isnan(num) or np.isinf(num):
        return None
    return num


def convertir_numero_obligatorio(valor_raw: Any, etiqueta: str) -> float:
    """
    Convierte un valor a float usando limpiar_numero_chileno o lanza
    ErrorValidacionCotizacion en español si no es numérico.
    """
    num = limpiar_numero_chileno(valor_raw)
    if num is None:
        raise ErrorValidacionCotizacion(
            f"El valor de '{etiqueta}' debe ser un número válido."
        )
    return num


def validar_rango_pert(
    v_min: Any, v_prob: Any, v_max: Any, etiqueta: str
) -> tuple[float, float, float]:
    """
    Valida que los tres parámetros PERT sean numéricos, no negativos y cumplan
    mínimo <= probable <= máximo.
    """
    a = limpiar_numero_chileno(v_min)
    m = limpiar_numero_chileno(v_prob)
    b = limpiar_numero_chileno(v_max)

    if a is None or m is None or b is None:
        raise ErrorValidacionCotizacion(
            f"Los valores mínimo, probable y máximo de '{etiqueta}' deben ser numéricos válidos."
        )

    if a < 0 or m < 0 or b < 0:
        raise ErrorValidacionCotizacion(
            f"En '{etiqueta}', los valores mínimo, probable y máximo no pueden ser negativos."
        )

    if a > m + 1e-9 or m > b + 1e-9:
        raise ErrorValidacionCotizacion(
            f"Rango inválido en '{etiqueta}': debe cumplirse Mínimo ({a:,.0f}) <= Probable ({m:,.0f}) <= Máximo ({b:,.0f})."
        )

    m = max(a, min(m, b))
    return a, m, b


def muestrear_pert_vectorizado(
    v_min: np.ndarray | float,
    v_prob: np.ndarray | float,
    v_max: np.ndarray | float,
    n_sim: int = 10000,
    rng: np.random.Generator | None = None,
    lambd: float = 4.0,
) -> np.ndarray:
    """
    Genera muestras aleatorias con distribución PERT (Beta escalada) de forma vectorizada.
    Si las entradas son arrays de longitud K, retorna una matriz (K, n_sim).
    Si las entradas son escalares, retorna un vector (n_sim,).
    """
    if rng is None:
        rng = np.random.default_rng()

    es_escalar = np.ndim(v_min) == 0 and np.ndim(v_prob) == 0 and np.ndim(v_max) == 0
    a = np.atleast_1d(np.asarray(v_min, dtype=np.float64))
    m = np.atleast_1d(np.asarray(v_prob, dtype=np.float64))
    b = np.atleast_1d(np.asarray(v_max, dtype=np.float64))

    if np.any(a > m + 1e-9) or np.any(m > b + 1e-9):
        raise ErrorValidacionCotizacion(
            "Error en distribución PERT: se requiere mínimo <= probable <= máximo."
        )

    k = a.shape[0]
    resultado = np.empty((k, n_sim), dtype=np.float64)
    rango = b - a
    constantes = rango <= 1e-9

    if np.any(constantes):
        resultado[constantes, :] = a[constantes, None]

    variables = ~constantes
    if np.any(variables):
        a_v = a[variables, None]
        m_v = m[variables, None]
        b_v = b[variables, None]
        r_v = rango[variables, None]

        alpha = 1.0 + lambd * ((m_v - a_v) / r_v)
        beta = 1.0 + lambd * ((b_v - m_v) / r_v)

        alpha = np.maximum(alpha, 1e-6)
        beta = np.maximum(beta, 1e-6)

        u = rng.beta(alpha, beta, size=(int(np.sum(variables)), n_sim))
        resultado[variables, :] = a_v + r_v * u

    return resultado[0] if es_escalar else resultado


def aplicar_correlacion_iman_conover(
    muestras: np.ndarray,
    mascara_cobre: np.ndarray,
    rng: np.random.Generator,
    rho_cobre: float = 0.88,
    rho_obra: float = 0.66,
) -> np.ndarray:
    """
    Correlaciona las muestras PERT preservando al 100% las distribuciones marginales exactas
    de cada partida mediante reordenamiento por rangos (Iman-Conover).
    - Las partidas sensibles al cobre comparten un factor común fuerte de mercado del cobre (z_cobre).
    - Todas las partidas de la obra comparten un factor moderado de complejidad/condición de obra (z_obra).
    """
    k, n_sim = muestras.shape
    if k <= 1:
        return muestras

    z_cobre = rng.standard_normal((1, n_sim))
    z_obra = rng.standard_normal((1, n_sim))
    eps = rng.standard_normal((k, n_sim))

    es_cobre = np.asarray(mascara_cobre, dtype=bool)[:, None]

    w_cobre_1 = np.sqrt(0.60)
    w_obra_1 = np.sqrt(0.28)
    w_eps_1 = np.sqrt(max(0.01, 1.0 - 0.60 - 0.28))

    w_obra_0 = np.sqrt(rho_obra)
    w_eps_0 = np.sqrt(max(0.01, 1.0 - rho_obra))

    puntajes = np.where(
        es_cobre,
        w_cobre_1 * z_cobre + w_obra_1 * z_obra + w_eps_1 * eps,
        w_obra_0 * z_obra + w_eps_0 * eps,
    )

    orden_latente = np.argsort(puntajes, axis=1)
    rangos = np.empty_like(orden_latente)
    filas = np.arange(k)[:, None]
    rangos[filas, orden_latente] = np.arange(n_sim)[None, :]

    muestras_ordenadas = np.sort(muestras, axis=1)
    return muestras_ordenadas[filas, rangos]


def ajustar_regresion_logistica(
    ratios: np.ndarray, resultados: np.ndarray, max_iter: int = 40
) -> tuple[float, float]:
    """
    Ajusta una regresión logística simple P(win | ratio) = 1 / (1 + exp(-(b0 + b1 * ratio)))
    donde ratio = precio_ofertado / costo_estimado y resultado in {0, 1}.
    """
    x = np.asarray(ratios, dtype=np.float64)
    y = np.asarray(resultados, dtype=np.float64)

    b0 = 8.75
    b1 = -7.0

    if x.size < 3:
        return b0, b1

    X = np.column_stack([np.ones_like(x), x])
    beta = np.array([b0, b1], dtype=np.float64)
    reg = np.diag([1e-3, 1e-2])

    for _ in range(max_iter):
        z = np.clip(X @ beta, -25.0, 25.0)
        p = 1.0 / (1.0 + np.exp(-z))
        w = np.maximum(p * (1.0 - p), 1e-5)
        grad = X.T @ (y - p) - reg @ (beta - np.array([8.75, -7.0]))
        H = (X.T * w) @ X + reg
        try:
            paso = np.linalg.solve(H, grad)
        except np.linalg.LinAlgError:
            break
        beta += paso
        if np.linalg.norm(paso) < 1e-6:
            break

    if beta[1] >= -0.8:
        beta[1] = -6.8
        beta[0] = -beta[1] * float(np.median(x))

    return float(beta[0]), float(beta[1])


def calcular_probabilidad_ganar(
    precios: np.ndarray | float,
    costo_esperado: float,
    calibracion: dict[str, Any] | None = None,
    superficie_m2: float = 120.0,
) -> np.ndarray:
    """
    Calcula P(win | precio) entre 0 y 1 para un vector o escalar de precios ofertados:
    a) Si calibracion['tipo'] == 'competencia':
       - Si el CSV trajo 'superficie_m2' (normalizado_m2=True), compara precio / superficie_m2
         contra la distribución empírica de precios por m² de la competencia.
       - Si no trajo 'superficie_m2', compara montos absolutos limitando P(win) con un piso
         razonable (10%) en lugar de caer a 1%.
    b) Si calibracion['tipo'] == 'historial': regresión logística sobre precio / costo_esperado.
    c) Si no hay datos: curva logística por defecto centrada en costo_esperado * 1.25.
    """
    es_escalar = np.ndim(precios) == 0
    p_arr = np.atleast_1d(np.asarray(precios, dtype=np.float64))
    c_esp = max(float(costo_esperado), 1.0)
    sup_m2 = max(float(superficie_m2 or 120.0), 1.0)

    if calibracion and calibracion.get("tipo") == "competencia":
        normalizado_m2 = bool(calibracion.get("normalizado_m2", False))
        if normalizado_m2 and calibracion.get("precios_m2_adjudicados"):
            muestra_comp = np.sort(
                np.asarray(calibracion["precios_m2_adjudicados"], dtype=np.float64)
            )
            valores_eval = p_arr / sup_m2
            piso_min = 0.05  # Piso razonable 5% cuando está normalizado por m²
        else:
            muestra_comp = np.sort(
                np.asarray(calibracion.get("precios_adjudicados", []), dtype=np.float64)
            )
            valores_eval = p_arr
            piso_min = 0.10  # Piso razonable 10% (nunca baja a 1%) cuando no está normalizado por tamaño

        if muestra_comp.size >= 2:
            n = muestra_comp.size
            # Interpolación empírica suavizada entre [piso_min, 0.98]
            prob_emp = piso_min + (0.98 - piso_min) * (
                1.0 - (np.arange(1, n + 1, dtype=np.float64) - 0.5) / n
            )
            x_min = muestra_comp[0] * 0.88
            x_max = muestra_comp[-1] * 1.12
            xp = np.concatenate([[x_min], muestra_comp, [x_max]])
            fp = np.concatenate([[0.98], prob_emp, [piso_min]])
            xp_unicos, idx_unicos = np.unique(xp, return_index=True)
            fp_unicos = fp[idx_unicos]
            probs = np.clip(np.interp(valores_eval, xp_unicos, fp_unicos), piso_min, 0.98)
            return probs[0] if es_escalar else probs

    if calibracion and calibracion.get("tipo") == "historial":
        b0 = float(calibracion.get("beta0", 9.0))
        b1 = float(calibracion.get("beta1", -7.2))
        ratios = p_arr / c_esp
        z = np.clip(b0 + b1 * ratios, -30.0, 30.0)
        probs = 1.0 / (1.0 + np.exp(-z))
        return probs[0] if es_escalar else probs

    # Modo c) Curva logística por defecto centrada en costo_esperado * 1.25 con pendiente moderada
    k = 7.2
    centro = 1.25
    ratios = p_arr / c_esp
    z = np.clip(k * (ratios - centro), -30.0, 30.0)
    probs = 1.0 / (1.0 + np.exp(z))
    return probs[0] if es_escalar else probs


def procesar_csv_calibracion(contenido_bytes: bytes, nombre_archivo: str = "datos.csv") -> dict[str, Any]:
    """
    Lee y valida un archivo CSV de calibración (competencia o historial) usando dtype=str
    y limpiar_numero_chileno (sin borrar puntos a ciegas).
    Descarta filas con celdas vacías o no numéricas e informa cuántas filas se descartaron.
    """
    texto = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            texto = contenido_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if not texto or not texto.strip():
        raise ErrorValidacionCotizacion("El archivo CSV está vacío o no pudo leerse.")

    primera_linea = texto.strip().splitlines()[0]
    sep = ";" if primera_linea.count(";") > primera_linea.count(",") else ","

    try:
        df = pd.read_csv(
            io.StringIO(texto),
            sep=sep,
            dtype=str,
            keep_default_na=False,
        )
    except Exception as exc:
        raise ErrorValidacionCotizacion(
            f"No se pudo interpretar el archivo CSV '{nombre_archivo}': {exc}"
        ) from exc

    columnas_norm = {col.strip().lower(): col for col in df.columns}
    total_filas = len(df)

    # Caso A: CSV de competencia (proyecto, rubro, precio_adjudicado, [superficie_m2], region, fecha)
    if "precio_adjudicado" in columnas_norm:
        col_precio = columnas_norm["precio_adjudicado"]
        tiene_col_m2 = "superficie_m2" in columnas_norm
        col_m2 = columnas_norm.get("superficie_m2")

        precios_validos = []
        precios_m2_validos = []
        registros_muestra = []
        filas_descartadas = 0

        for _, row in df.iterrows():
            precio_val = limpiar_numero_chileno(row.get(col_precio))
            if precio_val is None or precio_val <= 0:
                filas_descartadas += 1
                continue

            m2_val = None
            if tiene_col_m2 and col_m2:
                m2_val = limpiar_numero_chileno(row.get(col_m2))
                if m2_val is None or m2_val <= 0:
                    filas_descartadas += 1
                    continue
                precios_m2_validos.append(float(precio_val / m2_val))

            precios_validos.append(float(precio_val))
            if len(registros_muestra) < 50:
                registros_muestra.append(
                    {
                        "proyecto": str(row.get(columnas_norm.get("proyecto", ""), "")).strip() or "Proyecto",
                        "rubro": str(row.get(columnas_norm.get("rubro", ""), "")).strip() or "Eléctrico",
                        "superficie_m2": round(float(m2_val), 1) if m2_val is not None else None,
                        "precio_adjudicado": round(float(precio_val)),
                        "precio_m2": round(float(precio_val / m2_val)) if m2_val else None,
                        "region": str(row.get(columnas_norm.get("region", ""), "")).strip() or "Biobío",
                        "fecha": str(row.get(columnas_norm.get("fecha", ""), "")).strip(),
                    }
                )

        if len(precios_validos) < 3:
            raise ErrorValidacionCotizacion(
                f"El CSV de competencia debe contener al menos 3 filas válidas con precios positivos "
                f"(se descartaron {filas_descartadas} filas inválidas o vacías)."
            )

        precios_ordenados = [round(float(x), 2) for x in np.sort(np.asarray(precios_validos))]
        precios_m2_ordenados = (
            [round(float(x), 2) for x in np.sort(np.asarray(precios_m2_validos))]
            if tiene_col_m2
            else []
        )

        aviso_tamano = (
            None
            if tiene_col_m2
            else "Los precios no se normalizaron por tamaño; úsalos solo con obras de monto similar"
        )
        txt_descarte = (
            f" ({filas_descartadas} filas descartadas por celdas vacías o no numéricas)"
            if filas_descartadas > 0
            else " (0 filas descartadas)"
        )
        desc_norm = "normalizada por m²" if tiene_col_m2 else "sin normalizar por m²"

        return {
            "tipo": "competencia",
            "n_registros": len(precios_ordenados),
            "total_filas_leidas": total_filas,
            "filas_descartadas": filas_descartadas,
            "normalizado_m2": tiene_col_m2,
            "aviso_tamano": aviso_tamano,
            "precios_adjudicados": precios_ordenados,
            "precios_m2_adjudicados": precios_m2_ordenados,
            "mediana_clp": round(float(np.median(precios_ordenados))),
            "mediana_m2_clp": round(float(np.median(precios_m2_ordenados))) if precios_m2_ordenados else None,
            "promedio_clp": round(float(np.mean(precios_ordenados))),
            "min_clp": round(float(min(precios_ordenados))),
            "max_clp": round(float(max(precios_ordenados))),
            "registros": registros_muestra,
            "descripcion_metodo": (
                f"Distribución empírica de competencia {desc_norm} "
                f"({len(precios_ordenados)} licitaciones válidas){txt_descarte}"
            ),
        }

    # Caso B: CSV de historial (proyecto, costo_estimado, precio_ofertado, resultado)
    if {"costo_estimado", "precio_ofertado", "resultado"}.issubset(set(columnas_norm.keys())):
        c_costo = columnas_norm["costo_estimado"]
        c_precio = columnas_norm["precio_ofertado"]
        c_res = columnas_norm["resultado"]

        costos_validos = []
        precios_validos = []
        resultados_validos = []
        puntos = []
        filas_descartadas = 0

        for idx, row in df.iterrows():
            v_costo = limpiar_numero_chileno(row.get(c_costo))
            v_precio = limpiar_numero_chileno(row.get(c_precio))
            v_res = limpiar_numero_chileno(row.get(c_res))

            if (
                v_costo is None
                or v_costo <= 0
                or v_precio is None
                or v_precio <= 0
                or v_res is None
                or v_res not in (0.0, 1.0)
            ):
                filas_descartadas += 1
                continue

            costos_validos.append(float(v_costo))
            precios_validos.append(float(v_precio))
            resultados_validos.append(float(v_res))

            if len(puntos) < 50:
                nom_proy = (
                    str(row.get(columnas_norm["proyecto"], "")).strip()
                    if "proyecto" in columnas_norm
                    else ""
                ) or f"Cotización #{len(puntos) + 1}"
                puntos.append(
                    {
                        "proyecto": nom_proy,
                        "costo_estimado": round(float(v_costo)),
                        "precio_ofertado": round(float(v_precio)),
                        "ratio": round(float(v_precio / v_costo), 3),
                        "resultado": int(v_res),
                    }
                )

        if len(costos_validos) < 4:
            raise ErrorValidacionCotizacion(
                f"El CSV de historial requiere al menos 4 filas válidas con costo_estimado > 0, "
                f"precio_ofertado > 0 y resultado 0 o 1 (se descartaron {filas_descartadas} filas)."
            )

        ratios = np.asarray(precios_validos, dtype=np.float64) / np.asarray(
            costos_validos, dtype=np.float64
        )
        res_arr = np.asarray(resultados_validos, dtype=np.float64)
        b0, b1 = ajustar_regresion_logistica(ratios, res_arr)

        ratio_p50 = -b0 / b1 if abs(b1) > 1e-6 else 1.25
        txt_descarte = (
            f" ({filas_descartadas} filas descartadas por celdas vacías o no numéricas)"
            if filas_descartadas > 0
            else " (0 filas descartadas)"
        )

        return {
            "tipo": "historial",
            "n_registros": len(costos_validos),
            "total_filas_leidas": total_filas,
            "filas_descartadas": filas_descartadas,
            "normalizado_m2": True,
            "aviso_tamano": None,
            "beta0": round(b0, 4),
            "beta1": round(b1, 4),
            "ratio_p50": round(float(ratio_p50), 3),
            "tasa_exito_pct": round(float(np.mean(res_arr) * 100.0), 1),
            "puntos": puntos,
            "descripcion_metodo": (
                f"Regresión logística sobre historial propio ({len(costos_validos)} cotizaciones válidas){txt_descarte}"
            ),
        }

    raise ErrorValidacionCotizacion(
        "Formato CSV no reconocido. Use columnas 'proyecto, rubro, superficie_m2, precio_adjudicado, region, fecha' "
        "(competencia) o 'proyecto, costo_estimado, precio_ofertado, resultado' (historial)."
    )


def procesar_csv_base_costos(contenido_bytes: bytes) -> ListaPartidasCSV:
    """
    Parsea un CSV de base de costos con dtype=str y limpiar_numero_chileno:
    descripcion, unidad, precio_min, precio_probable, precio_max
    (y opcionales categoria, cantidad, merma_pct, valor_hora, sensible_cobre, sensible_dolar).
    Descarta filas con celdas vacías o no numéricas e informa cuántas filas se descartaron.
    """
    texto = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            texto = contenido_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if not texto or not texto.strip():
        raise ErrorValidacionCotizacion("El archivo CSV de base de costos está vacío.")

    primera_linea = texto.strip().splitlines()[0]
    sep = ";" if primera_linea.count(";") > primera_linea.count(",") else ","
    df = pd.read_csv(
        io.StringIO(texto),
        sep=sep,
        dtype=str,
        keep_default_na=False,
    )
    cols = {c.strip().lower(): c for c in df.columns}

    requeridas = {"descripcion", "unidad", "precio_min", "precio_probable", "precio_max"}
    faltantes = requeridas - set(cols.keys())
    if faltantes:
        raise ErrorValidacionCotizacion(
            f"Faltan columnas requeridas en la base de costos CSV: {', '.join(sorted(faltantes))}."
        )

    partidas = []
    filas_descartadas = 0
    total_filas = len(df)

    for _, row in df.iterrows():
        desc = str(row.get(cols["descripcion"], "")).strip()
        unidad = str(row.get(cols["unidad"], "")).strip()
        p_min = limpiar_numero_chileno(row.get(cols["precio_min"]))
        p_prob = limpiar_numero_chileno(row.get(cols["precio_probable"]))
        p_max = limpiar_numero_chileno(row.get(cols["precio_max"]))

        if (
            not desc
            or desc.lower() == "nan"
            or not unidad
            or p_min is None
            or p_prob is None
            or p_max is None
            or p_min < 0
            or p_prob < 0
            or p_max < 0
            or p_min > p_prob + 1e-9
            or p_prob > p_max + 1e-9
        ):
            filas_descartadas += 1
            continue

        cat_raw = (
            str(row.get(cols["categoria"], "")).strip().lower()
            if "categoria" in cols
            else "materiales"
        )
        cat = (
            cat_raw
            if cat_raw in ("materiales", "mano_obra", "subcontratos", "imprevistos")
            else "materiales"
        )

        cant = 1.0
        if "cantidad" in cols and str(row.get(cols["cantidad"], "")).strip():
            cant_parsed = limpiar_numero_chileno(row.get(cols["cantidad"]))
            if cant_parsed is None or (cat != "imprevistos" and cant_parsed <= 0):
                filas_descartadas += 1
                continue
            cant = cant_parsed

        merma = 5.0 if cat == "materiales" else 0.0
        if "merma_pct" in cols and str(row.get(cols["merma_pct"], "")).strip():
            merma_parsed = limpiar_numero_chileno(row.get(cols["merma_pct"]))
            if merma_parsed is None or merma_parsed < 0 or merma_parsed > 200:
                filas_descartadas += 1
                continue
            merma = merma_parsed

        v_hora = 9500.0 if cat == "mano_obra" else 0.0
        if "valor_hora" in cols and str(row.get(cols["valor_hora"], "")).strip():
            vh_parsed = limpiar_numero_chileno(row.get(cols["valor_hora"]))
            if vh_parsed is None or (cat == "mano_obra" and vh_parsed <= 0):
                filas_descartadas += 1
                continue
            v_hora = vh_parsed

        # Sensibilidad al cobre
        if "sensible_cobre" in cols and str(row.get(cols["sensible_cobre"], "")).strip():
            val_sc = str(row.get(cols["sensible_cobre"], "")).strip().lower()
            sens_cobre = val_sc in ("1", "true", "si", "sí", "yes")
        else:
            palabras_cobre = ("cable", "thhn", "cobre", "tablero", "automático", "automatico", "diferencial", "tierra")
            sens_cobre = any(p in desc.lower() for p in palabras_cobre)

        # Sensibilidad al dólar (independiente del cobre)
        if "sensible_dolar" in cols and str(row.get(cols["sensible_dolar"], "")).strip():
            val_sd = str(row.get(cols["sensible_dolar"], "")).strip().lower()
            sens_dolar = val_sd in ("1", "true", "si", "sí", "yes")
        else:
            palabras_dolar = ("led", "luminaria", "panel", "tablero", "automático", "automatico", "diferencial")
            sens_dolar = any(p in desc.lower() for p in palabras_dolar)

        partidas.append(
            {
                "orden": len(partidas) + 1,
                "categoria": cat,
                "descripcion": desc,
                "unidad": unidad,
                "cantidad": cant,
                "valor_min": p_min,
                "valor_prob": p_prob,
                "valor_max": p_max,
                "merma_pct": merma if cat == "materiales" else 0.0,
                "valor_hora": v_hora if cat == "mano_obra" else 0.0,
                "sensible_cobre": sens_cobre,
                "sensible_dolar": sens_dolar,
            }
        )

    if not partidas:
        raise ErrorValidacionCotizacion(
            f"No se encontraron partidas válidas en el CSV de costos "
            f"(se descartaron {filas_descartadas} filas con celdas vacías o no numéricas)."
        )

    return ListaPartidasCSV(
        partidas, filas_descartadas=filas_descartadas, total_filas=total_filas
    )


def evaluar_precio_puntual(
    precio_ofertado: Any,
    costos_simulados: np.ndarray,
    costo_esperado: float,
    calibracion: dict[str, Any] | None = None,
    superficie_m2: float = 120.0,
) -> dict[str, Any]:
    """
    Evalúa un precio ofertado puntual frente al vector de costos simulados.
    Valida que el precio ofertado sea numérico y estrictamente mayor que cero.
    """
    p = convertir_numero_obligatorio(precio_ofertado, "Precio ofertado")
    if p <= 0:
        raise ErrorValidacionCotizacion(
            "El precio ofertado debe ser mayor que cero (no puede ser negativo ni cero)."
        )

    prob_perdida = float(np.mean(costos_simulados > p) * 100.0)
    prob_ganar_dinero = 100.0 - prob_perdida
    prob_win = float(
        calcular_probabilidad_ganar(p, costo_esperado, calibracion, superficie_m2=superficie_m2)
    )
    margen_clp = float(p - costo_esperado)
    margen_pct = float((margen_clp / p) * 100.0) if p > 0 else 0.0
    ganancia_esp = float(prob_win * margen_clp)

    p_ganar_str = f"{prob_ganar_dinero:.1f}%".replace(".", ",")
    p_perdida_str = f"{prob_perdida:.1f}%".replace(".", ",")

    if prob_perdida < 10.0:
        semaforo = "verde"
        mensaje = (
            f"Con este precio hay {p_ganar_str} de probabilidad de ganar dinero "
            f"(riesgo de pérdida bajo: {p_perdida_str})."
        )
    elif prob_perdida <= 25.0:
        semaforo = "amarillo"
        mensaje = (
            f"Precaución: con este precio hay {p_ganar_str} de probabilidad de ganar dinero "
            f"y un riesgo moderado de pérdida de {p_perdida_str}."
        )
    else:
        semaforo = "rojo"
        mensaje = (
            f"Alerta de sobrecosto: con este precio hay {p_perdida_str} de probabilidad de perder plata "
            f"(solo {p_ganar_str} de salir con ganancia)."
        )

    return {
        "precio_ofertado_clp": round(p),
        "prob_perdida_pct": round(prob_perdida, 1),
        "prob_ganar_dinero_pct": round(prob_ganar_dinero, 1),
        "prob_ganar_licitacion_pct": round(prob_win * 100.0, 1),
        "margen_esperado_clp": round(margen_clp),
        "margen_esperado_pct": round(margen_pct, 1),
        "margen_sobre_costo_pct": round(((p - costo_esperado) / max(costo_esperado, 1.0)) * 100.0, 1),
        "ganancia_esperada_clp": round(ganancia_esp),
        "semaforo": semaforo,
        "mensaje_semaforo": mensaje,
    }


def simular_cotizacion(
    partidas: list[dict[str, Any]],
    var_cobre: Any = 0.0,
    var_dolar: Any = 0.0,
    sens_cobre: Any = 0.6,
    sens_dolar: Any = 0.3,
    gg_min: Any = 8.0,
    gg_prob: Any = 11.0,
    gg_max: Any = 16.0,
    utilidad_deseada: Any = 20.0,
    superficie_m2: Any = 120.0,
    n_simulaciones: int = 10000,
    semilla: int | None = 42,
    calibracion: dict[str, Any] | None = None,
    precio_ofertado_usuario: Any = None,
) -> dict[str, Any]:
    """
    Ejecuta la simulación Montecarlo PERT de 10.000 escenarios sobre las partidas de la cotización,
    aplicando el slider de cobre solo a partidas sensibles al cobre y el slider de dólar solo
    a partidas sensibles al dólar.
    """
    t0 = time.perf_counter()

    if not partidas or not isinstance(partidas, list):
        raise ErrorValidacionCotizacion(
            "La cotización debe incluir al menos una partida para ejecutar la simulación."
        )

    # Validar parámetros macro y de proyecto en español
    v_cobre = convertir_numero_obligatorio(var_cobre, "Variación del cobre (%)")
    v_dolar = convertir_numero_obligatorio(var_dolar, "Variación del dólar (%)")
    s_cobre = convertir_numero_obligatorio(sens_cobre, "Sensibilidad al cobre")
    s_dolar = convertir_numero_obligatorio(sens_dolar, "Sensibilidad al dólar")
    _ = convertir_numero_obligatorio(utilidad_deseada, "Utilidad deseada (%)")
    sup_m2 = convertir_numero_obligatorio(superficie_m2, "Superficie (m²)")
    if sup_m2 <= 0:
        raise ErrorValidacionCotizacion("La superficie en m² debe ser mayor que cero.")

    # Validar precio ofertado si fue enviado explícitamente
    precio_usr_validado: float | None = None
    if precio_ofertado_usuario is not None and str(precio_ofertado_usuario).strip() != "":
        precio_usr_validado = convertir_numero_obligatorio(
            precio_ofertado_usuario, "Precio ofertado"
        )
        if precio_usr_validado <= 0:
            raise ErrorValidacionCotizacion(
                "El precio ofertado debe ser mayor que cero (no puede ser negativo ni cero)."
            )

    gg_a, gg_m, gg_b = validar_rango_pert(gg_min, gg_prob, gg_max, "Gastos Generales (%)")

    # Clasificar y validar cada partida
    partidas_limpias = []
    for idx, p in enumerate(partidas):
        desc = str(p.get("descripcion", "")).strip() or f"Partida #{idx + 1}"
        cat = str(p.get("categoria", "materiales")).strip().lower()
        if cat not in ("materiales", "mano_obra", "subcontratos", "imprevistos"):
            raise ErrorValidacionCotizacion(f"Categoría inválida '{cat}' en '{desc}'.")

        cantidad = convertir_numero_obligatorio(
            p.get("cantidad", 1.0), f"Cantidad en '{desc}'"
        )
        if cat != "imprevistos" and cantidad <= 0:
            raise ErrorValidacionCotizacion(
                f"La cantidad en '{desc}' debe ser mayor que cero."
            )
        if cat == "imprevistos" and cantidad <= 0:
            cantidad = 1.0

        v_min, v_prob, v_max = validar_rango_pert(
            p.get("valor_min", 0),
            p.get("valor_prob", 0),
            p.get("valor_max", 0),
            desc,
        )

        merma_raw = p.get("merma_pct", 0.0)
        merma_pct = (
            0.0
            if merma_raw in (None, "")
            else convertir_numero_obligatorio(merma_raw, f"Merma (%) en '{desc}'")
        )
        if merma_pct < 0 or merma_pct > 200:
            raise ErrorValidacionCotizacion(
                f"El porcentaje de merma en '{desc}' debe estar entre 0% y 200%."
            )

        vh_raw = p.get("valor_hora", 0.0)
        valor_hora = (
            0.0
            if vh_raw in (None, "")
            else convertir_numero_obligatorio(vh_raw, f"Valor hora en '{desc}'")
        )
        if cat == "mano_obra" and valor_hora <= 0:
            raise ErrorValidacionCotizacion(
                f"El valor hora en '{desc}' (Mano de obra) debe ser mayor que cero."
            )

        sensible_cobre = bool(p.get("sensible_cobre", False))
        sensible_dolar = bool(p.get("sensible_dolar", False))

        # Factor de ajuste de mercado individual por partida (cobre y dólar independientes)
        delta_cobre = (s_cobre * (v_cobre / 100.0)) if sensible_cobre else 0.0
        delta_dolar = (s_dolar * (v_dolar / 100.0)) if sensible_dolar else 0.0
        factor_partida = max(0.15, 1.0 + delta_cobre + delta_dolar)

        partidas_limpias.append(
            {
                "orden": idx + 1,
                "categoria": cat,
                "descripcion": desc,
                "unidad": str(p.get("unidad", "un")),
                "cantidad": cantidad,
                "valor_min": v_min,
                "valor_prob": v_prob,
                "valor_max": v_max,
                "merma_pct": merma_pct if cat == "materiales" else 0.0,
                "valor_hora": valor_hora if cat == "mano_obra" else 0.0,
                "sensible_cobre": sensible_cobre,
                "sensible_dolar": sensible_dolar,
                "factor_mercado": factor_partida,
            }
        )

    rng = np.random.default_rng(semilla)
    k = len(partidas_limpias)

    # Preparar vectores PERT con ajuste de mercado independiente (cobre / dólar) antes de simular
    vec_min = np.array(
        [p["valor_min"] * p["factor_mercado"] for p in partidas_limpias],
        dtype=np.float64,
    )
    vec_prob = np.array(
        [p["valor_prob"] * p["factor_mercado"] for p in partidas_limpias],
        dtype=np.float64,
    )
    vec_max = np.array(
        [p["valor_max"] * p["factor_mercado"] for p in partidas_limpias],
        dtype=np.float64,
    )
    mascara_cobre = np.array([p["sensible_cobre"] for p in partidas_limpias], dtype=bool)

    muestras_base = muestrear_pert_vectorizado(
        vec_min, vec_prob, vec_max, n_sim=n_simulaciones, rng=rng
    )
    if muestras_base.ndim == 1:
        muestras_base = muestras_base[None, :]

    muestras_corr = aplicar_correlacion_iman_conover(
        muestras_base, mascara_cobre=mascara_cobre, rng=rng
    )

    matriz_costos = np.zeros((k, n_simulaciones), dtype=np.float64)
    indices_imprevistos = []

    for i, p in enumerate(partidas_limpias):
        cat = p["categoria"]
        if cat == "materiales":
            matriz_costos[i, :] = (
                p["cantidad"] * (1.0 + p["merma_pct"] / 100.0) * muestras_corr[i, :]
            )
        elif cat == "mano_obra":
            matriz_costos[i, :] = p["cantidad"] * muestras_corr[i, :] * p["valor_hora"]
        elif cat == "subcontratos":
            matriz_costos[i, :] = p["cantidad"] * muestras_corr[i, :]
        elif cat == "imprevistos":
            indices_imprevistos.append(i)

    costo_directo_sin_imprevistos = np.sum(matriz_costos, axis=0)

    for i in indices_imprevistos:
        p = partidas_limpias[i]
        if np.mean(costo_directo_sin_imprevistos) > 0:
            matriz_costos[i, :] = (
                costo_directo_sin_imprevistos * (muestras_corr[i, :] / 100.0) * p["cantidad"]
            )
        else:
            matriz_costos[i, :] = p["cantidad"] * muestras_corr[i, :]

    costo_directo_total = np.sum(matriz_costos, axis=0)

    gg_pct_sim = muestrear_pert_vectorizado(
        gg_a, gg_m, gg_b, n_sim=n_simulaciones, rng=rng
    )
    orden_cd = np.argsort(costo_directo_total)
    rangos_cd = np.empty_like(orden_cd)
    rangos_cd[orden_cd] = np.arange(n_simulaciones)
    ruido_gg = 0.65 * rangos_cd + 0.35 * np.argsort(np.argsort(gg_pct_sim))
    gg_pct_corr = np.sort(gg_pct_sim)[np.argsort(np.argsort(ruido_gg))]

    costo_indirecto_sim = costo_directo_total * (gg_pct_corr / 100.0)
    costo_total_sim = costo_directo_total + costo_indirecto_sim

    costo_esperado = float(np.mean(costo_total_sim))
    costo_p50 = float(np.percentile(costo_total_sim, 50))
    costo_p80 = float(np.percentile(costo_total_sim, 80))
    costo_p90 = float(np.percentile(costo_total_sim, 90))
    desv_estandar = float(np.std(costo_total_sim))
    costo_min_sim = float(np.min(costo_total_sim))
    costo_max_sim = float(np.max(costo_total_sim))

    base_grilla = max(costo_p50, 1.0)
    grilla_precios = np.linspace(base_grilla * 0.95, base_grilla * 1.80, 100)

    costos_ordenados = np.sort(costo_total_sim)
    idx_superados = np.searchsorted(costos_ordenados, grilla_precios, side="right")
    prob_perdida_grilla = (1.0 - idx_superados / float(n_simulaciones)) * 100.0

    prob_win_grilla = calcular_probabilidad_ganar(
        grilla_precios,
        costo_esperado=costo_esperado,
        calibracion=calibracion,
        superficie_m2=sup_m2,
    )
    margen_esperado_grilla = grilla_precios - costo_esperado
    ganancia_esperada_grilla = prob_win_grilla * margen_esperado_grilla

    idx_optimo = int(np.argmax(ganancia_esperada_grilla))
    precio_optimo = float(grilla_precios[idx_optimo])

    mascara_seguro = prob_perdida_grilla <= 10.0
    if np.any(mascara_seguro):
        precio_min_seguro = float(grilla_precios[int(np.argmax(mascara_seguro))])
        precio_min_seguro = max(precio_min_seguro, costo_p90)
    else:
        precio_min_seguro = float(costo_p90)

    precio_ingenuo_20 = float(costo_esperado * 1.20)
    eval_ingenuo = evaluar_precio_puntual(
        precio_ingenuo_20, costo_total_sim, costo_esperado, calibracion, superficie_m2=sup_m2
    )
    eval_optimo = evaluar_precio_puntual(
        precio_optimo, costo_total_sim, costo_esperado, calibracion, superficie_m2=sup_m2
    )

    precio_ofertado = (
        precio_usr_validado if precio_usr_validado is not None else precio_optimo
    )
    eval_ofertado = evaluar_precio_puntual(
        precio_ofertado, costo_total_sim, costo_esperado, calibracion, superficie_m2=sup_m2
    )

    desglose_categorias = {
        "materiales": 0.0,
        "mano_obra": 0.0,
        "subcontratos": 0.0,
        "imprevistos": 0.0,
        "gastos_generales": float(np.mean(costo_indirecto_sim)),
    }
    for i, p in enumerate(partidas_limpias):
        desglose_categorias[p["categoria"]] += float(np.mean(matriz_costos[i, :]))

    diff_total = costo_total_sim - costo_esperado
    covs = np.maximum(
        0.0,
        np.mean(
            (matriz_costos - np.mean(matriz_costos, axis=1, keepdims=True))
            * diff_total[None, :],
            axis=1,
        ),
    )
    suma_covs = float(np.sum(covs))
    if suma_covs <= 1e-9:
        medias_partidas = np.mean(matriz_costos, axis=1)
        suma_medias = float(np.sum(medias_partidas)) or 1.0
        aportes_riesgo = (medias_partidas / suma_medias) * 100.0
    else:
        aportes_riesgo = (covs / suma_covs) * 100.0

    ranking_partidas = []
    for i, p in enumerate(partidas_limpias):
        c_fila = matriz_costos[i, :]
        c_esp_i = float(np.mean(c_fila))
        c_p10_i = float(np.percentile(c_fila, 10))
        c_p90_i = float(np.percentile(c_fila, 90))
        ranking_partidas.append(
            {
                "orden": p["orden"],
                "descripcion": p["descripcion"],
                "categoria": p["categoria"],
                "unidad": p["unidad"],
                "cantidad": p["cantidad"],
                "sensible_cobre": p["sensible_cobre"],
                "sensible_dolar": p["sensible_dolar"],
                "costo_esperado_clp": round(c_esp_i),
                "costo_p10_clp": round(c_p10_i),
                "costo_p90_clp": round(c_p90_i),
                "desviacion_baja_clp": round(c_p10_i - c_esp_i),
                "desviacion_alta_clp": round(c_p90_i - c_esp_i),
                "amplitud_riesgo_clp": round(c_p90_i - c_p10_i),
                "aporte_costo_pct": round((c_esp_i / max(costo_esperado, 1.0)) * 100.0, 1),
                "aporte_riesgo_pct": round(float(aportes_riesgo[i]), 1),
            }
        )

    ranking_partidas.sort(
        key=lambda item: (item["aporte_riesgo_pct"], item["amplitud_riesgo_clp"]),
        reverse=True,
    )

    conteos_hist, bordes_hist = np.histogram(costo_total_sim, bins=28)
    centros_hist = 0.5 * (bordes_hist[:-1] + bordes_hist[1:])
    histograma = {
        "centros_clp": [round(float(x)) for x in centros_hist],
        "bordes_clp": [round(float(x)) for x in bordes_hist],
        "frecuencias": [int(c) for c in conteos_hist],
        "probabilidades_pct": [round(float(c / n_simulaciones * 100.0), 2) for c in conteos_hist],
    }

    grilla_cuantiles = np.linspace(0, 100, 201)
    valores_cuantiles = np.percentile(costo_total_sim, grilla_cuantiles)

    if calibracion and calibracion.get("tipo") in ("competencia", "historial"):
        info_calibracion = {
            "modo": calibracion["tipo"],
            "es_generica": False,
            "n_registros": int(calibracion.get("n_registros", 0)),
            "filas_descartadas": int(calibracion.get("filas_descartadas", 0)),
            "normalizado_m2": bool(calibracion.get("normalizado_m2", True)),
            "aviso_tamano": calibracion.get("aviso_tamano"),
            "descripcion": calibracion.get("descripcion_metodo", "Curva calibrada con CSV"),
            "es_demo": bool(calibracion.get("es_demo", False)),
        }
    else:
        info_calibracion = {
            "modo": "por_defecto",
            "es_generica": True,
            "n_registros": 0,
            "filas_descartadas": 0,
            "normalizado_m2": True,
            "aviso_tamano": None,
            "descripcion": (
                "Curva logística genérica centrada en Costo Esperado × 1,25 (sin CSV de competencia cargado)"
            ),
            "es_demo": True,
        }

    factor_cobre_ref = max(0.15, 1.0 + s_cobre * (v_cobre / 100.0))
    factor_dolar_ref = max(0.15, 1.0 + s_dolar * (v_dolar / 100.0))
    tiempo_ms = round((time.perf_counter() - t0) * 1000.0, 1)

    return {
        "resumen": {
            "costo_esperado_clp": round(costo_esperado),
            "costo_p50_clp": round(costo_p50),
            "costo_p80_clp": round(costo_p80),
            "costo_p90_clp": round(costo_p90),
            "desv_estandar_clp": round(desv_estandar),
            "costo_min_clp": round(costo_min_sim),
            "costo_max_clp": round(costo_max_sim),
            "punto_equilibrio_clp": round(costo_esperado),
            "precio_min_seguro_clp": round(precio_min_seguro),
            "precio_optimo_clp": round(precio_optimo),
            "precio_ingenuo_clp": round(precio_ingenuo_20),
            "costo_directo_esperado_clp": round(float(np.mean(costo_directo_total))),
            "costo_indirecto_esperado_clp": round(float(np.mean(costo_indirecto_sim))),
            "superficie_m2": round(sup_m2, 1),
            "costo_esperado_m2_clp": round(costo_esperado / sup_m2),
            "precio_optimo_m2_clp": round(precio_optimo / sup_m2),
            "ajuste_cobre_factor": round(factor_cobre_ref, 4),
            "ajuste_dolar_factor": round(factor_dolar_ref, 4),
            "var_cobre_pct": float(v_cobre),
            "var_dolar_pct": float(v_dolar),
            "sens_cobre": float(s_cobre),
            "sens_dolar": float(s_dolar),
            "n_simulaciones": int(n_simulaciones),
            "tiempo_calculo_ms": tiempo_ms,
        },
        "evaluacion_ofertado": eval_ofertado,
        "evaluacion_optimo": eval_optimo,
        "evaluacion_ingenuo": eval_ingenuo,
        "curva_precio_optimo": {
            "precios_clp": [round(float(p)) for p in grilla_precios],
            "prob_ganar_pct": [round(float(pw * 100.0), 1) for pw in prob_win_grilla],
            "prob_perdida_pct": [round(float(pl), 1) for pl in prob_perdida_grilla],
            "margen_si_gana_clp": [round(float(m)) for m in margen_esperado_grilla],
            "ganancia_esperada_clp": [round(float(g)) for g in ganancia_esperada_grilla],
            "indice_optimo": idx_optimo,
            "precio_optimo_clp": round(precio_optimo),
            "ganancia_maxima_clp": round(float(ganancia_esperada_grilla[idx_optimo])),
        },
        "histograma": histograma,
        "desglose_categorias": {
            k_cat: round(v_cat) for k_cat, v_cat in desglose_categorias.items()
        },
        "ranking_riesgo": ranking_partidas,
        "cuantiles_costo_clp": [round(float(v)) for v in valores_cuantiles],
        "calibracion_info": info_calibracion,
    }
