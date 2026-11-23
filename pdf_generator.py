"""
Generador de Propuesta Comercial en PDF profesional con ReportLab para CotizaSmart.
Trabajo 3 - Tecnología de la Información II, Universidad de Concepción (Campus Los Ángeles).
Autores: Jorge Campos, Benjamin Muñoz y Raul Vergara.
"""

from __future__ import annotations
import io
from typing import Any
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)


def formatear_clp(monto: float | int) -> str:
    """Formatea un número en pesos chilenos con punto como separador de miles, sin decimales."""
    valor = int(round(float(monto or 0)))
    signo = "-" if valor < 0 else ""
    texto = f"{abs(valor):,}".replace(",", ".")
    return f"{signo}${texto}"


def calcular_desglose_comercial_cliente(cotizacion_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Calcula el desglose comercial para el cliente (vista previa y PDF) prorrateando el
    Precio Neto Ofertado entre las categorías y partidas según su peso esperado,
    de modo que NO se expongan costos internos, mermas, rangos min/max ni márgenes,
    y la suma cuadre al peso exacto con el Precio Neto Ofertado.
    """
    precio_neto = int(round(float(cotizacion_dict.get("precio_ofertado_clp") or 0)))
    partidas = cotizacion_dict.get("partidas", [])

    # Calcular peso base de cada partida usando su valor esperado PERT
    pesos_partidas = []
    for p in partidas:
        cat = p.get("categoria", "materiales")
        v_min = float(p.get("valor_min", 0))
        v_prob = float(p.get("valor_prob", 0))
        v_max = float(p.get("valor_max", 0))
        media_pert = (v_min + 4.0 * v_prob + v_max) / 6.0
        cant = float(p.get("cantidad", 1.0) or 1.0)

        if cat == "materiales":
            merma = float(p.get("merma_pct", 0.0) or 0.0)
            costo_base = cant * (1.0 + merma / 100.0) * media_pert
        elif cat == "mano_obra":
            v_hora = float(p.get("valor_hora", 0.0) or 0.0)
            costo_base = cant * media_pert * v_hora
        elif cat == "subcontratos":
            costo_base = cant * media_pert
        else:
            costo_base = 0.0  # Imprevistos se absorben proporcionalmente en el precio comercial

        pesos_partidas.append((p, cat, max(costo_base, 0.0)))

    suma_directa = sum(x[2] for x in pesos_partidas)
    if suma_directa <= 0:
        suma_directa = 1.0

    etiquetas_cat = {
        "materiales": "1. Suministro de Materiales, Canalización y Equipos Eléctricos",
        "mano_obra": "2. Mano de Obra Especializada, Montaje y Conexionado",
        "subcontratos": "3. Ingeniería, Certificación SEC (TE1), Pruebas y Equipos de Apoyo",
    }

    totales_cat = {"materiales": 0, "mano_obra": 0, "subcontratos": 0}
    items_comerciales = []

    acumulado = 0
    partidas_visibles = [x for x in pesos_partidas if x[1] in totales_cat]
    if not partidas_visibles:
        # Si solo había una partida de imprevistos
        partidas_visibles = [(p, "subcontratos", 1.0) for p, _, _ in pesos_partidas]
        suma_directa = float(len(partidas_visibles) or 1)

    for idx, (p, cat, peso) in enumerate(partidas_visibles):
        if idx == len(partidas_visibles) - 1:
            subtotal_comercial = max(0, precio_neto - acumulado)
        else:
            subtotal_comercial = int(round(precio_neto * (peso / suma_directa)))
            acumulado += subtotal_comercial

        totales_cat[cat] = totales_cat.get(cat, 0) + subtotal_comercial
        cant = float(p.get("cantidad", 1.0) or 1.0)
        p_unit_comercial = int(round(subtotal_comercial / max(cant, 1.0)))

        items_comerciales.append(
            {
                "item": idx + 1,
                "categoria": cat,
                "categoria_nombre": etiquetas_cat.get(cat, "Otros"),
                "descripcion": p.get("descripcion", "Partida eléctrica"),
                "unidad": "gl" if p.get("unidad") == "HH" else p.get("unidad", "un"),
                "cantidad": 1 if p.get("unidad") == "HH" else (int(cant) if cant.is_integer() else round(cant, 1)),
                "precio_unitario_clp": subtotal_comercial if p.get("unidad") == "HH" else p_unit_comercial,
                "subtotal_clp": subtotal_comercial,
            }
        )

    resumen_categorias = []
    for clave, nombre_cat in etiquetas_cat.items():
        monto_cat = totales_cat.get(clave, 0)
        if monto_cat > 0:
            pct = round((monto_cat / max(precio_neto, 1)) * 100.0, 1)
            resumen_categorias.append(
                {
                    "codigo": clave,
                    "nombre": nombre_cat,
                    "monto_clp": monto_cat,
                    "porcentaje": pct,
                }
            )

    iva_clp = int(round(precio_neto * 0.19))
    total_con_iva_clp = precio_neto + iva_clp

    return {
        "precio_neto_clp": precio_neto,
        "iva_clp": iva_clp,
        "total_con_iva_clp": total_con_iva_clp,
        "resumen_categorias": resumen_categorias,
        "items_comerciales": items_comerciales,
    }


def generar_pdf_propuesta(cotizacion_dict: dict[str, Any]) -> bytes:
    """
    Genera el archivo PDF de la propuesta comercial para el cliente y retorna sus bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=15 * mm,
        bottomMargin=16 * mm,
        title=f"Propuesta Comercial {cotizacion_dict.get('codigo', 'CotizaSmart')}",
        author="CotizaSmart - Ingeniería Eléctrica",
    )

    estilos = getSampleStyleSheet()
    azul_primario = colors.HexColor("#0F172A")
    azul_acento = colors.HexColor("#1E3A8A")
    verde_esmeralda = colors.HexColor("#059669")
    gris_texto = colors.HexColor("#334155")
    gris_suave = colors.HexColor("#F8FAFC")
    gris_borde = colors.HexColor("#CBD5E1")

    estilo_titulo_seccion = ParagraphStyle(
        "TituloSeccion",
        parent=estilos["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=13,
        textColor=azul_acento,
        spaceBefore=8,
        spaceAfter=4,
    )
    estilo_normal = ParagraphStyle(
        "TextoNormal",
        parent=estilos["Normal"],
        fontName="Helvetica",
        fontSize=8.8,
        leading=12,
        textColor=gris_texto,
    )
    estilo_celda = ParagraphStyle(
        "TextoCelda",
        parent=estilos["Normal"],
        fontName="Helvetica",
        fontSize=8.2,
        leading=10.5,
        textColor=gris_texto,
    )
    estilo_celda_bold = ParagraphStyle(
        "TextoCeldaBold",
        parent=estilo_celda,
        fontName="Helvetica-Bold",
        textColor=azul_primario,
    )
    estilo_pie = ParagraphStyle(
        "TextoPie",
        parent=estilos["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#64748B"),
        alignment=1,
    )

    elementos = []
    desglose = calcular_desglose_comercial_cliente(cotizacion_dict)

    # 1. Encabezado Corporativo
    codigo = cotizacion_dict.get("codigo", "COT-2026-001")
    fecha = cotizacion_dict.get("fecha_creacion", "22-11-2026")
    validez = cotizacion_dict.get("validez_dias", 15)

    encabezado_izq = Paragraph(
        "<font size=15 color='#FFFFFF'><b>CotizaSmart</b></font><br/>"
        "<font size=7.8 color='#93C5FD'>INGENIERÍA Y PROYECTOS ELÉCTRICOS · NORMATIVA SEC RIC CHILE</font>",
        estilo_normal,
    )
    encabezado_der = Paragraph(
        f"<para align='right'><font size=10 color='#FFFFFF'><b>PROPUESTA TÉCNICA Y COMERCIAL</b></font><br/>"
        f"<font size=8 color='#E2E8F0'>N° {codigo} · Fecha: {fecha} · Validez: {validez} días</font></para>",
        estilo_normal,
    )
    tabla_header = Table([[encabezado_izq, encabezado_der]], colWidths=[94 * mm, 84 * mm])
    tabla_header.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), azul_primario),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    elementos.append(tabla_header)
    elementos.append(Spacer(1, 4 * mm))

    # 2. Datos del Cliente y del Proyecto
    elementos.append(Paragraph("1. ANTECEDENTES DEL CLIENTE Y PROYECTO", estilo_titulo_seccion))
    filas_info = [
        [
            Paragraph("<b>Cliente / Mandante:</b>", estilo_celda_bold),
            Paragraph(str(cotizacion_dict.get("cliente", "")), estilo_celda),
            Paragraph("<b>RUT Cliente:</b>", estilo_celda_bold),
            Paragraph(str(cotizacion_dict.get("rut_cliente", "76.548.320-4")), estilo_celda),
        ],
        [
            Paragraph("<b>Proyecto:</b>", estilo_celda_bold),
            Paragraph(str(cotizacion_dict.get("nombre", "")), estilo_celda),
            Paragraph("<b>Ubicación / Ciudad:</b>", estilo_celda_bold),
            Paragraph(str(cotizacion_dict.get("ciudad", "Los Ángeles")), estilo_celda),
        ],
        [
            Paragraph("<b>Especialidad:</b>", estilo_celda_bold),
            Paragraph(str(cotizacion_dict.get("tipo_proyecto", "")), estilo_celda),
            Paragraph("<b>Plazo de Ejecución:</b>", estilo_celda_bold),
            Paragraph(f"{cotizacion_dict.get('plazo_dias', 20)} días corridos", estilo_celda),
        ],
        [
            Paragraph("<b>Superficie Intervenida:</b>", estilo_celda_bold),
            Paragraph(f"{float(cotizacion_dict.get('superficie_m2', 120)):.0f} m²", estilo_celda),
            Paragraph("<b>Puntos Eléctricos:</b>", estilo_celda_bold),
            Paragraph(f"{cotizacion_dict.get('puntos_electricos', 45)} puntos", estilo_celda),
        ],
    ]
    tabla_info = Table(filas_info, colWidths=[36 * mm, 62 * mm, 36 * mm, 44 * mm])
    tabla_info.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), gris_suave),
                ("GRID", (0, 0), (-1, -1), 0.5, gris_borde),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elementos.append(tabla_info)

    # 3. Alcance Técnico
    elementos.append(Paragraph("2. ALCANCE TÉCNICO DE LA OFERTA", estilo_titulo_seccion))
    alcance_txt = cotizacion_dict.get("alcance_propuesta") or (
        "Suministro, canalización, cableado, montaje de tableros, protecciones "
        "termomagnéticas y diferenciales, instalación de luminarias LED, enchufes, "
        "puesta a tierra y tramitación de certificación TE1 ante la SEC."
    )
    elementos.append(Paragraph(alcance_txt, estilo_normal))
    elementos.append(Spacer(1, 2 * mm))

    # 4. Resumen por Categoría Comercial
    elementos.append(Paragraph("3. RESUMEN COMERCIAL POR CATEGORÍA", estilo_titulo_seccion))
    filas_cat = [
        [
            Paragraph("<b>Categoría del Alcance</b>", estilo_celda_bold),
            Paragraph("<para align='right'><b>Incidencia</b></para>", estilo_celda_bold),
            Paragraph("<para align='right'><b>Valor Neto (CLP)</b></para>", estilo_celda_bold),
        ]
    ]
    for c_item in desglose["resumen_categorias"]:
        pct_str = f"{c_item['porcentaje']:.1f}%".replace(".", ",")
        filas_cat.append(
            [
                Paragraph(c_item["nombre"], estilo_celda),
                Paragraph(f"<para align='right'>{pct_str}</para>", estilo_celda),
                Paragraph(
                    f"<para align='right'><b>{formatear_clp(c_item['monto_clp'])}</b></para>",
                    estilo_celda,
                ),
            ]
        )

    tabla_cat = Table(filas_cat, colWidths=[116 * mm, 26 * mm, 36 * mm])
    tabla_cat.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                ("GRID", (0, 0), (-1, -1), 0.5, gris_borde),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elementos.append(tabla_cat)

    # 5. Detalle de Partidas Cotizadas (sin márgenes ni rangos internos)
    elementos.append(Paragraph("4. DETALLE DE PARTIDAS INCLUIDAS", estilo_titulo_seccion))
    filas_det = [
        [
            Paragraph("<b>Ítem</b>", estilo_celda_bold),
            Paragraph("<b>Descripción de la Partida</b>", estilo_celda_bold),
            Paragraph("<para align='center'><b>Unid.</b></para>", estilo_celda_bold),
            Paragraph("<para align='right'><b>Cant.</b></para>", estilo_celda_bold),
            Paragraph("<para align='right'><b>P. Unitario</b></para>", estilo_celda_bold),
            Paragraph("<para align='right'><b>Subtotal Neto</b></para>", estilo_celda_bold),
        ]
    ]
    for it in desglose["items_comerciales"]:
        filas_det.append(
            [
                Paragraph(str(it["item"]), estilo_celda),
                Paragraph(str(it["descripcion"]), estilo_celda),
                Paragraph(f"<para align='center'>{it['unidad']}</para>", estilo_celda),
                Paragraph(f"<para align='right'>{it['cantidad']}</para>", estilo_celda),
                Paragraph(
                    f"<para align='right'>{formatear_clp(it['precio_unitario_clp'])}</para>",
                    estilo_celda,
                ),
                Paragraph(
                    f"<para align='right'>{formatear_clp(it['subtotal_clp'])}</para>",
                    estilo_celda,
                ),
            ]
        )

    tabla_det = Table(
        filas_det,
        colWidths=[11 * mm, 89 * mm, 14 * mm, 14 * mm, 24 * mm, 26 * mm],
        repeatRows=1,
    )
    tabla_det.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, gris_suave]),
                ("GRID", (0, 0), (-1, -1), 0.4, gris_borde),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    elementos.append(tabla_det)
    elementos.append(Spacer(1, 4 * mm))

    # 6. Cuadro de Totales (Neto, IVA 19%, Total) y Condiciones Comerciales
    condiciones_pago = cotizacion_dict.get(
        "condiciones_pago",
        "50% anticipo contra orden de compra, 50% contra recepción conforme y entrega de certificado TE1 SEC.",
    )
    bloque_condiciones = Paragraph(
        f"<b>Condiciones Comerciales:</b><br/>"
        f"• <b>Forma de pago:</b> {condiciones_pago}<br/>"
        f"• <b>Validez de la oferta:</b> {validez} días corridos desde la fecha de emisión.<br/>"
        f"• <b>Garantía técnica:</b> 12 meses por montaje e instalación conforme a pliegos RIC SEC.",
        estilo_celda,
    )

    filas_totales = [
        [
            Paragraph("<b>SUBTOTAL NETO:</b>", estilo_celda_bold),
            Paragraph(
                f"<para align='right'><b>{formatear_clp(desglose['precio_neto_clp'])}</b></para>",
                estilo_celda_bold,
            ),
        ],
        [
            Paragraph("<b>IVA (19%):</b>", estilo_celda_bold),
            Paragraph(
                f"<para align='right'><b>{formatear_clp(desglose['iva_clp'])}</b></para>",
                estilo_celda_bold,
            ),
        ],
        [
            Paragraph(
                "<font color='#FFFFFF'><b>TOTAL OFERTA (CLP):</b></font>",
                estilo_celda_bold,
            ),
            Paragraph(
                f"<para align='right'><font size=10 color='#FFFFFF'><b>{formatear_clp(desglose['total_con_iva_clp'])}</b></font></para>",
                estilo_celda_bold,
            ),
        ],
    ]
    tabla_totales = Table(filas_totales, colWidths=[38 * mm, 34 * mm])
    tabla_totales.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 1), gris_suave),
                ("BACKGROUND", (0, 2), (-1, 2), verde_esmeralda),
                ("GRID", (0, 0), (-1, -1), 0.5, gris_borde),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )

    tabla_cierre = Table(
        [[bloque_condiciones, tabla_totales]], colWidths=[104 * mm, 74 * mm]
    )
    tabla_cierre.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    elementos.append(tabla_cierre)
    elementos.append(Spacer(1, 7 * mm))

    # 7. Pie de página institucional
    elementos.append(HRFlowable(width="100%", thickness=0.6, color=gris_borde))
    elementos.append(Spacer(1, 2 * mm))
    elementos.append(
        Paragraph(
            "CotizaSmart - Proyecto TI II, Universidad de Concepción, Campus Los Ángeles. "
            "Jorge Campos, Benjamin Muñoz, Raul Vergara.",
            estilo_pie,
        )
    )

    doc.build(elementos)
    return buffer.getvalue()
