"""
Generador de PDF para informes radiológicos usando ReportLab (RF-24).

Produce un PDF profesional con:
- Identificación del estudio y datos del paciente
- Técnica, hallazgos, impresión y recomendaciones
- Advertencia sobre el carácter preliminar del apoyo IA
- Firma del médico radiólogo

Mantiene el mismo contenido semántico que el template HTML existente
(informes/informe_pdf.html) pero usando ReportLab como motor principal.
"""

from io import BytesIO
from xml.sax.saxutils import escape
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether,
)
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.pdfbase.pdfmetrics import stringWidth


# ──────────────────────────────────────────────────────────────────────────────
# ESTILOS
# ──────────────────────────────────────────────────────────────────────────────

def _build_styles():
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "NeoRxTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0d9488"),
        spaceAfter=2,
    )
    subtitle_style = ParagraphStyle(
        "NeoRxSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#64748b"),
        alignment=TA_CENTER,
        spaceAfter=8,
    )
    section_style = ParagraphStyle(
        "NeoRxSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#0d9488"),
        spaceBefore=10,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "NeoRxBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=15,
        textColor=colors.HexColor("#1f2937"),
        alignment=TA_LEFT,
        spaceAfter=6,
    )
    info_label_style = ParagraphStyle(
        "NeoRxInfoLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#374151"),
    )
    info_value_style = ParagraphStyle(
        "NeoRxInfoValue",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1f2937"),
    )
    warning_style = ParagraphStyle(
        "NeoRxWarning",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#92400e"),
        backColor=colors.HexColor("#fef3c7"),
        borderColor=colors.HexColor("#f59e0b"),
        borderWidth=0.7,
        borderPadding=8,
        spaceBefore=12,
        spaceAfter=12,
    )
    footer_style = ParagraphStyle(
        "NeoRxFooter",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#94a3b8"),
        alignment=TA_CENTER,
    )
    return {
        "title": title_style,
        "subtitle": subtitle_style,
        "section": section_style,
        "body": body_style,
        "info_label": info_label_style,
        "info_value": info_value_style,
        "warning": warning_style,
        "footer": footer_style,
    }


def _sanitize(text):
    """Convierte a str seguro y limpia caracteres incompatibles con Helvetica."""
    if text is None:
        return ""
    return escape(str(text)).replace("\n", "<br/>")


def _edad(paciente, hoy=None):
    hoy = hoy or datetime.today().date()
    nac = paciente.fecha_nacimiento
    return (
        hoy.year - nac.year
        - ((hoy.month, hoy.day) < (nac.month, nac.day))
    )


def _draw_footer(canvas, doc):
    """Footer con número de página y nota legal."""
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#94a3b8"))
    canvas.drawCentredString(
        A4[0] / 2, 1.2 * cm,
        "Informe generado por Sistema Neo RX - Apoyo a la Interpretación Radiológica | Página {}".format(doc.page)
    )
    canvas.restoreState()


def generar_pdf_informe(informe, contexto=None) -> BytesIO:
    """
    Genera el PDF del informe con ReportLab.

    Args:
        informe: Instancia de InformePreliminar con estudio, paciente, medico.
        contexto: Dict opcional con campos adicionales
            (medico_nombre, fecha_firmado, fecha_hoy, estudio_fecha, edad).

    Returns:
        BytesIO con el contenido PDF.
    """
    contexto = contexto or {}
    styles = _build_styles()

    estudio = informe.estudio
    paciente = estudio.paciente
    medico = informe.medico
    medico_nombre = contexto.get("medico_nombre") or (medico.get_full_name() if medico else None)
    fecha_firmado = contexto.get("fecha_firmado") or (
        informe.fecha_firmado.strftime("%d/%m/%Y %H:%M") if informe.fecha_firmado else None
    )
    fecha_hoy = contexto.get("fecha_hoy") or datetime.today().strftime("%d/%m/%Y")
    estudio_fecha = contexto.get("estudio_fecha") or estudio.fecha.strftime("%d/%m/%Y")
    edad = contexto.get("edad") or _edad(paciente)
    proyeccion = contexto.get("proyeccion") or getattr(
        estudio.imagenes.first(), "tipo_proyeccion", "PA"
    )

    story = []

    # ── Encabezado ──
    story.append(Paragraph("INFORME RADIOLÓGICO", styles["title"]))
    story.append(Paragraph("Centro: Neo Rayos X Digital — La Paz, Bolivia", styles["subtitle"]))
    story.append(Paragraph(
        "Fecha emisión: {} | Informe N°: {} | Estado: {}".format(
            fecha_hoy, estudio.id, _sanitize(informe.estado).upper()
        ),
        styles["subtitle"],
    ))
    story.append(HRFlowable(width="100%", thickness=1.2, color=colors.HexColor("#0d9488"), spaceAfter=10))

    # ── Datos del paciente ──
    datos = [
        ["Paciente:", "{} {}".format(paciente.apellidos, paciente.nombres)],
        ["CI:", _sanitize(paciente.ci)],
        ["Edad:", "{} años".format(edad)],
        ["Sexo:", _sanitize(paciente.get_genero_display())],
        ["Estudio:", _sanitize(estudio.tipo_estudio)],
        ["Fecha estudio:", estudio_fecha],
        ["Proyección:", _sanitize(proyeccion)],
        ["Médico:", _sanitize(medico_nombre or "—")],
        ["Fecha firma:", _sanitize(fecha_firmado or "—")],
    ]
    rows = []
    for label, value in datos:
        rows.append([
            Paragraph(label, styles["info_label"]),
            Paragraph(_sanitize(value), styles["info_value"]),
        ])
    tabla = Table(rows, colWidths=[3.5 * cm, 13 * cm])
    tabla.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
    ]))
    story.append(tabla)
    story.append(Spacer(1, 8))

    # ── Secciones clínicas ──
    secciones = [
        ("TÉCNICA", _sanitize(informe.tecnica)),
        ("HALLAZGOS", _sanitize(informe.hallazgos)),
        ("IMPRESIÓN DIAGNÓSTICA", _sanitize(informe.impresion)),
        ("RECOMENDACIONES", _sanitize(informe.recomendaciones)),
    ]
    for titulo, contenido in secciones:
        story.extend([
            Paragraph(titulo, styles["section"]),
            Paragraph(contenido or "—", styles["body"]),
        ])

    # ── Advertencia IA ──
    story.append(Paragraph(
        "<b>⚠ ADVERTENCIA IMPORTANTE:</b> Este informe constituye un apoyo preliminar "
        "para la interpretación radiológica basado en análisis asistido por IA (CNN ResNet-50). "
        "No sustituye la evaluación, validación y firma del médico radiólogo especialista. "
        "Los hallazgos y probabilidades son estimaciones asistidas por computadora y requieren "
        "correlación clínica obligatoria por parte del profesional médico responsable.",
        styles["warning"],
    ))

    # ── Firma ──
    story.append(Spacer(1, 24))
    firma = Table(
        [[Paragraph(
            "{}<br/><font size=8 color='#64748b'>Médico Radiólogo Especialista<br/>"
            "Neo Rayos X Digital — La Paz, Bolivia</font>".format(
                _sanitize(medico_nombre or "Dr. Médico Radiólogo")
            ),
            ParagraphStyle("firma", parent=styles["info_value"], alignment=TA_CENTER, fontSize=10, leading=13),
        )]],
        colWidths=[8 * cm],
    )
    firma.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("LINEABOVE", (0, 0), (-1, 0), 0.8, colors.HexColor("#475569")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(firma)

    # ── Construir documento ──
    buffer = BytesIO()
    doc = pdfcanvas.Canvas(buffer, pagesize=A4)
    doc.setTitle("Informe Radiológico - {}".format(estudio.id))
    doc.setAuthor("Neo Rayos X Digital")
    doc.setSubject("Informe radiológico asistido por IA")

    from reportlab.platypus import SimpleDocTemplate
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="Informe Radiológico - {}".format(estudio.id),
        author="Neo Rayos X Digital",
    )
    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    buffer.seek(0)
    return buffer
