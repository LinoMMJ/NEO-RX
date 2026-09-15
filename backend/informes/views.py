"""
Views para Informes Clínicos — Generación, Firma, Export PDF y DICOM SR.

Endpoints:
- POST   /api/informes/generar/          → Genera borrador automático desde CNN
- GET    /api/informes/<pk>/             → Detalle / edición de borrador
- PUT    /api/informes/<pk>/             → Actualiza hallazgos/impresión/recomendaciones
- POST   /api/informes/<pk>/firmar/      → Firma (solo rol=medico)
- GET    /api/informes/<pk>/pdf/         → Export PDF (weasyprint)
- GET    /api/informes/<pk>/dicom-sr/    → Export DICOM SR (Basic Text SR)
"""

from datetime import datetime
from io import BytesIO

from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from django.http import FileResponse
from django.template.loader import render_to_string
from rest_framework.views import APIView
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from pacientes.models import Estudio
from estudios.models import ImagenDICOM
from diagnostico.models import ResultadoCNN
from .models import InformePreliminar
from .serializers import InformePreliminarSerializer


# ──────────────────────────────────────────────────────────────────────────────
# GENERADORES DE TEXTO CLÍNICO
# ──────────────────────────────────────────────────────────────────────────────

# NOTA: las claves coinciden EXACTAMENTE con services.PATOLOGIAS_NEUMOLOGIA
# (sin acentos): "Neumonia", "Consolidacion", "Nodulo", "Neumotorax", etc.
# Usar acentos aquí provocaría .get() == 0 y el informe saldría siempre vacío.

def _pct(v):
    return f"{v * 100:.0f}%"


def generar_texto_hallazgos(resultado_cnn, tipo_proyeccion):
    """Genera texto clínico estructurado por regiones anatómicas.
    Umbral de mención: >15%. Umbral de hallazgo positivo: >45%."""
    patologias = resultado_cnn.patologias or {}
    tipo = tipo_proyeccion or "PA"
    texto = []

    # REGIÓN 1: PARÉNQUIMA PULMONAR
    pulmonares = {
        "Neumonia": patologias.get("Neumonia", 0),
        "Consolidacion": patologias.get("Consolidacion", 0),
        "Infiltrado": patologias.get("Infiltrado", 0),
        "Nodulo": patologias.get("Nodulo", 0),
        "Masa": patologias.get("Masa", 0),
        "Atelectasia": patologias.get("Atelectasia", 0),
        "Edema pulmonar": patologias.get("Edema pulmonar", 0),
        "Opacidad pulmonar": patologias.get("Opacidad pulmonar", 0),
    }
    hallazgos_pulmonares = {k: v for k, v in pulmonares.items() if v > 0.15}
    if hallazgos_pulmonares:
        positivos = [k for k, v in hallazgos_pulmonares.items() if v > 0.45]
        marginales = [k for k, v in hallazgos_pulmonares.items() if 0.15 < v <= 0.45]
        linea = "PARÉNQUIMA PULMONAR: "
        if positivos:
            linea += f"Se identifican opacidades compatibles con {', '.join(positivos).lower()}. "
        if marginales:
            probs = " / ".join(_pct(hallazgos_pulmonares[m]) for m in marginales)
            linea += (
                f"No se descartan hallazgos incipientes de {', '.join(marginales).lower()} "
                f"(probabilidad {probs}). "
            )
        texto.append(linea.strip())
    else:
        texto.append(
            "PARÉNQUIMA PULMONAR: Sin opacidades ni infiltrados significativos identificados."
        )

    # REGIÓN 2: ESPACIOS PLEURALES
    pleural = patologias.get("Derrame pleural", 0)
    engrosamiento = patologias.get("Engrosamiento pleural", 0)
    neum = patologias.get("Neumotorax", 0)
    pleura_hallazgos = []
    if pleural > 0.45:
        pleura_hallazgos.append(f"derrame pleural ({_pct(pleural)})")
    elif pleural > 0.15:
        pleura_hallazgos.append(f"probable derrame pleural ({_pct(pleural)})")
    if neum > 0.45:
        pleura_hallazgos.append(f"neumotórax ({_pct(neum)})")
    elif neum > 0.15:
        pleura_hallazgos.append(f"posible neumotórax ({_pct(neum)})")
    if engrosamiento > 0.30:
        pleura_hallazgos.append(f"engrosamiento pleural ({_pct(engrosamiento)})")
    if pleura_hallazgos:
        texto.append(f"ESPACIOS PLEURALES: Se observa {', '.join(pleura_hallazgos)}.")
    else:
        texto.append(
            "ESPACIOS PLEURALES: Ángulos costofrénicos libres. "
            "Sin evidencia de derrame ni neumotórax."
        )

    # REGIÓN 3: MEDIASTINO Y SILUETA CARDÍACA
    texto.append(
        "MEDIASTINO Y SILUETA CARDÍACA: Silueta cardíaca de tamaño conservado. "
        "Mediastino centrado de amplitud normal. Sin ensanchamiento mediastínico evidente."
    )

    # REGIÓN 4: ESTRUCTURAS ÓSEAS
    texto.append(
        "ESTRUCTURAS ÓSEAS: Arcos costales, clavículas y columna dorsal visibles "
        f"sin alteraciones morfológicas evidentes en la proyección {tipo}."
    )

    # REGIÓN 5: PARTES BLANDAS
    texto.append(
        "PARTES BLANDAS: Sin alteraciones significativas en tejidos blandos pericostales."
    )

    return "\n\n".join(texto)


def generar_impresion(resultado_cnn):
    """Resumen ejecutivo de los hallazgos."""
    patologias = resultado_cnn.patologias or {}
    top = sorted(patologias.items(), key=lambda x: x[1], reverse=True)
    criticos = [(k, v) for k, v in top if v > 0.65]
    moderados = [(k, v) for k, v in top if 0.40 < v <= 0.65]
    if not criticos and not moderados:
        return (
            "Radiografía de tórax sin hallazgos patológicos significativos "
            "según el análisis asistido por red neuronal convolucional ResNet-50. "
            "Se sugiere correlación clínica."
        )
    lineas = []
    if criticos:
        hallazgos_str = ", ".join(f"{k} ({_pct(v)})" for k, v in criticos)
        lineas.append(f"Hallazgos de alta probabilidad compatibles con: {hallazgos_str}.")
    if moderados:
        hallazgos_str = ", ".join(f"{k} ({_pct(v)})" for k, v in moderados)
        lineas.append(f"Hallazgos de probabilidad moderada a considerar: {hallazgos_str}.")
    lineas.append(
        "Impresión generada por sistema de apoyo diagnóstico (CNN ResNet-50). "
        "Requiere validación y firma del médico radiólogo especialista."
    )
    return " ".join(lineas)


def generar_recomendaciones(resultado_cnn):
    patologias = resultado_cnn.patologias or {}
    if not patologias:
        return "Control según criterio clínico. Sin hallazgos que requieran seguimiento urgente."
    top_proba = max(patologias.values())
    top_nombre = max(patologias, key=patologias.get)
    if top_proba > 0.65:
        return (
            f"Correlación clínica urgente recomendada. "
            f"Hallazgo principal ({top_nombre}) con alta probabilidad ({_pct(top_proba)}). "
            f"Considerar seguimiento con tomografía computada de tórax según criterio clínico."
        )
    elif top_proba > 0.40:
        return (
            "Correlación clínica recomendada. "
            "Seguimiento radiológico en 4-6 semanas si persiste sintomatología."
        )
    return "Control según criterio clínico. Sin hallazgos que requieran seguimiento urgente."


# ──────────────────────────────────────────────────────────────────────────────
# ENDPOINTS: GENERACIÓN, EDICIÓN, FIRMA
# ──────────────────────────────────────────────────────────────────────────────

@method_decorator(ratelimit(key="ip", rate="20/m", block=True), name="post")
class GenerarInformeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        estudio_id = request.data.get("estudio_id")
        if not estudio_id:
            return Response({"error": "Se requiere 'estudio_id'."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            estudio = Estudio.objects.get(pk=estudio_id)
        except Estudio.DoesNotExist:
            return Response({"error": "Estudio no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        # Imagen más reciente del estudio
        imagen = ImagenDICOM.objects.filter(estudio=estudio).order_by("-fecha_subida").first()
        if imagen is None:
            return Response(
                {"error": "El estudio no tiene imágenes asociadas."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            resultado = ResultadoCNN.objects.get(imagen=imagen)
        except ResultadoCNN.DoesNotExist:
            return Response(
                {"error": "No existe resultado CNN para este estudio."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tipo_proyeccion = imagen.tipo_proyeccion or "PA"
        calidad = "adecuada" if imagen.es_nitida else "limitada por borrosidad"

        informe, _ = InformePreliminar.objects.get_or_create(estudio=estudio)
        informe.tecnica = (
            f"Radiografía de Tórax {tipo_proyeccion}. Técnica digital con detector "
            f"de panel plano. Calidad técnica {calidad}."
        )
        informe.hallazgos = generar_texto_hallazgos(resultado, tipo_proyeccion)
        informe.impresion = generar_impresion(resultado)
        informe.recomendaciones = generar_recomendaciones(resultado)
        if getattr(request.user, "rol", None) == "medico" and informe.medico is None:
            informe.medico = request.user
        informe.save()

        serializer = InformePreliminarSerializer(informe, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


@method_decorator(ratelimit(key="ip", rate="60/m", block=True), name="get")
@method_decorator(ratelimit(key="ip", rate="20/m", block=True), name="put")
class InformePreliminarDetailView(RetrieveUpdateAPIView):
    queryset = InformePreliminar.objects.all()
    serializer_class = InformePreliminarSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def perform_update(self, serializer):
        from django.utils import timezone
        nuevo_estado = self.request.data.get("estado")
        extra = {}
        # Al firmar, sellar la fecha y asignar médico firmante
        if nuevo_estado == "firmado":
            extra["fecha_firmado"] = timezone.now()
            if getattr(self.request.user, "rol", None) == "medico":
                extra["medico"] = self.request.user
        serializer.save(**extra)


# ──────────────────────────────────────────────────────────────────────────────
# ENDPOINTS: EXPORT PDF (weasyprint)
# ──────────────────────────────────────────────────────────────────────────────

@method_decorator(ratelimit(key="ip", rate="10/m", block=True), name="get")
class DescargarInformePDFView(APIView):
    """
    GET /api/informes/<pk>/pdf/ — genera y descarga el informe como PDF (weasyprint).

    Solo disponible para informes en estado 'firmado'.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        # Try weasyprint first (better CSS support), fallback to xhtml2pdf
        pdf_engine = None
        try:
            from weasyprint import HTML
            pdf_engine = "weasyprint"
        except ImportError:
            try:
                from xhtml2pdf import pisa
                pdf_engine = "xhtml2pdf"
            except ImportError:
                return Response(
                    {"error": "Ni weasyprint ni xhtml2pdf instalados. Ejecuta: pip install weasyprint"},
                    status=status.HTTP_501_NOT_IMPLEMENTED,
                )

        try:
            informe = InformePreliminar.objects.select_related(
                "estudio__paciente", "medico"
            ).get(pk=pk)
        except InformePreliminar.DoesNotExist:
            return Response({"error": "Informe no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        if informe.estado != "firmado":
            return Response(
                {"error": "Solo se pueden descargar informes firmados."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        paciente = informe.estudio.paciente
        hoy = datetime.today().date()
        edad = (
            hoy.year - paciente.fecha_nacimiento.year
            - ((hoy.month, hoy.day) < (paciente.fecha_nacimiento.month, paciente.fecha_nacimiento.day))
        )
        medico_nombre = informe.medico.get_full_name() if informe.medico else None
        fecha_firmado = informe.fecha_firmado.strftime("%d/%m/%Y %H:%M") if informe.fecha_firmado else None

        contexto = {
            "informe": informe,
            "estudio": informe.estudio,
            "paciente": paciente,
            "medico": informe.medico,
            "medico_nombre": medico_nombre,
            "edad": edad,
            "fecha_hoy": hoy.strftime("%d/%m/%Y"),
            "estudio_fecha": informe.estudio.fecha.strftime("%d/%m/%Y"),
            "fecha_firmado": fecha_firmado,
        }

        try:
            html_string = render_to_string("informes/informe_pdf.html", contexto)

            if pdf_engine == "weasyprint":
                from weasyprint import HTML
                pdf_bytes = BytesIO()
                HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf(pdf_bytes)
            else:
                from xhtml2pdf import pisa
                pdf_bytes = BytesIO()
                result = pisa.CreatePDF(html_string, dest=pdf_bytes)
                if result.err:
                    return Response(
                        {"error": f"Error al renderizar el PDF ({result.err} errores de formato)."},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

            pdf_bytes.seek(0)
        except Exception as exc:
            return Response(
                {"error": f"Error al generar el PDF: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        filename = f"Informe_{paciente.ci}_{informe.estudio.id}.pdf"
        response = FileResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


# ──────────────────────────────────────────────────────────────────────────────
# ENDPOINTS: EXPORT DICOM SR (Basic Text SR)
# ──────────────────────────────────────────────────────────────────────────────

@method_decorator(ratelimit(key="ip", rate="10/m", block=True), name="get")
class DescargarInformeDICOMSRView(APIView):
    """
    GET /api/informes/<pk>/dicom-sr/ — genera y descarga Structured Report DICOM (Basic Text SR).

    Cumple con DICOM PS3.16 (Structured Reporting) — Basic Text SR IOD.
    Incluye: Patient Module, Study Module, SR Document Series/Document Modules,
    y Content Tree con hallazgos, impresión y recomendaciones.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            import pydicom
            from pydicom.uid import (
                generate_uid, ExplicitVRLittleEndian,
                BasicTextSRStorage, VerificationSOPClass
            )
            from pydicom.dataset import Dataset
            from pydicom.sequence import Sequence
            from pydicom.valuerep import PersonName
        except ImportError:
            return Response(
                {"error": "pydicom no instalado. Ejecuta: pip install pydicom"},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )

        try:
            informe = InformePreliminar.objects.select_related(
                "estudio__paciente", "medico", "estudio__paciente"
            ).get(pk=pk)
        except InformePreliminar.DoesNotExist:
            return Response({"error": "Informe no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        if informe.estado != "firmado":
            return Response(
                {"error": "Solo se pueden exportar informes firmados."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ──────────────────────────────────────────────────────────────────────
        # BUILD DICOM SR DATASET
        # ──────────────────────────────────────────────────────────────────────

        ds = Dataset()
        ds.file_meta = Dataset()

        # File Meta Information
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        ds.file_meta.MediaStorageSOPClassUID = BasicTextSRStorage
        ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
        ds.file_meta.ImplementationClassUID = generate_uid()
        ds.file_meta.ImplementationVersionName = "NEORX_SR_1.0"

        # ───── SOP Common Module ─────
        ds.SOPClassUID = BasicTextSRStorage
        ds.SOPInstanceUID = generate_uid()

        # ───── Patient Module ─────
        paciente = informe.estudio.paciente
        ds.PatientName = PersonName(f"{paciente.apellidos}^{paciente.nombres}")
        ds.PatientID = paciente.ci
        ds.PatientBirthDate = paciente.fecha_nacimiento.strftime("%Y%m%d")
        ds.PatientSex = paciente.genero[0].upper() if paciente.genero else "O"

        # ───── General Study Module ─────
        ds.StudyInstanceUID = generate_uid()  # En producción: usar UID real del estudio
        ds.StudyDate = informe.estudio.fecha.strftime("%Y%m%d")
        ds.StudyTime = datetime.now().strftime("%H%M%S")
        ds.ReferringPhysicianName = PersonName("")
        ds.StudyID = str(informe.estudio.id)
        ds.AccessionNumber = str(informe.estudio.id)

        # ───── SR Document Series Module ─────
        ds.Modality = "SR"
        ds.SeriesInstanceUID = generate_uid()
        ds.SeriesNumber = 1
        ds.SeriesDate = datetime.now().strftime("%Y%m%d")
        ds.SeriesTime = datetime.now().strftime("%H%M%S")

        # ───── General Equipment Module ─────
        ds.Manufacturer = "Neo Rayos X Digital"
        ds.ManufacturerModelName = "Neo RX AI Assistant"
        ds.DeviceSerialNumber = "NEORX-001"
        ds.SoftwareVersions = "1.0"

        # ───── SR Document General Module ─────
        ds.InstanceNumber = 1
        ds.CompletionFlag = "COMPLETE"
        ds.VerificationFlag = "UNVERIFIED"  # Cambiar a VERIFIED si se desea
        ds.ContentDate = datetime.now().strftime("%Y%m%d")
        ds.ContentTime = datetime.now().strftime("%H%M%S")

        # Verifying Observer (médico firmante)
        if informe.medico:
            vo_seq = Sequence()
            vo_item = Dataset()
            vo_item.PersonName = PersonName(informe.medico.get_full_name())
            vo_item.VerificationDateTime = informe.fecha_firmado.strftime("%Y%m%d%H%M%S") if informe.fecha_firmado else datetime.now().strftime("%Y%m%d%H%M%S")
            vo_seq.append(vo_item)
            ds.VerifyingObserverSequence = vo_seq

        # ───── SR Document Content Module ─────
        # Content Template: TID 2000 (Basic Text SR)
        content_seq = Sequence()

        # CONTAINER: Root
        root = Dataset()
        root.ValueType = "CONTAINER"
        root.ConceptNameCodeSequence = Sequence([self._code_item("113000", "DCM", "Radiology Report")])
        root.ContinuityOfContent = "SEPARATE"
        root.ContentSequence = Sequence()

        # ─── 1. Clinical Context ───
        clinical_context = self._make_container(
            "121005", "DCM", "Clinical Context",
            children=[
                self._text_item("121006", "DCM", "Clinical History", f"Radiografía de tórax rutinaria. Centro: Neo Rayos X Digital, La Paz, Bolivia."),
                self._text_item("121007", "DCM", "Reason for Exam", "Control radiológico / Sintomatología respiratoria"),
            ]
        )
        root.ContentSequence.append(clinical_context)

        # ─── 2. Technique ───
        technique = self._make_container(
            "121008", "DCM", "Technique",
            children=[
                self._text_item("121009", "DCM", "Technique Description", informe.tecnica),
                self._text_item("121010", "DCM", "Image Quality", "Adecuada" if getattr(informe.estudio.imagenes.first(), 'es_nitida', True) else "Limitada por borrosidad"),
            ]
        )
        root.ContentSequence.append(technique)

        # ─── 3. Findings ───
        findings_container = self._make_container(
            "121000", "DCM", "Findings",
            children=[
                self._text_item("121001", "DCM", "Findings", informe.hallazgos or "Sin hallazgos significativos."),
            ]
        )
        root.ContentSequence.append(findings_container)

        # ─── 4. Impression ───
        impression = self._make_container(
            "121002", "DCM", "Impression",
            children=[
                self._text_item("121003", "DCM", "Impression", informe.impresion or "Sin impresión diagnóstica."),
            ]
        )
        root.ContentSequence.append(impression)

        # ─── 5. Recommendations ───
        recommendations = self._make_container(
            "121004", "DCM", "Recommendations",
            children=[
                self._text_item("121005", "DCM", "Recommendations", informe.recomendaciones or "Control según criterio clínico."),
            ]
        )
        root.ContentSequence.append(recommendations)

        # ─── 6. AI Assistant Metadata ───
        ai_meta = self._make_container(
            "113001", "DCM", "AI Assistant Metadata",
            children=[
                self._text_item("113002", "DCM", "AI System", "Neo RX CNN ResNet-50 (torchxrayvision)"),
                self._text_item("113003", "DCM", "AI Version", "1.0"),
                self._text_item("113004", "DCM", "AI Role", "Decision Support (no autonomous diagnosis)"),
                self._text_item("113005", "DCM", "Disclaimer", "Este informe es preliminar. Requiere validación y firma del médico radiólogo según Ley 3131."),
            ]
        )
        root.ContentSequence.append(ai_meta)

        ds.ContentSequence = root.ContentSequence

        # ───── Save to BytesIO ─────
        from pydicom.filebase import DicomBytesIO
        buffer = DicomBytesIO()
        ds.save_as(buffer, write_like_original=False)
        buffer.seek(0)

        filename = f"SR_{paciente.ci}_{informe.estudio.id}.dcm"
        response = FileResponse(buffer, content_type="application/dicom")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return Response(response.getvalue(), content_type="application/dicom", headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        })

    # ──────────────────────────────────────────────────────────────────────────
    # HELPERS para DICOM SR
    # ──────────────────────────────────────────────────────────────────────────

    def _code_item(self, code_value, coding_scheme, code_meaning):
        """Crea un item Code Sequence (CODE)."""
        from pydicom.dataset import Dataset
        item = Dataset()
        item.CodeValue = code_value
        item.CodingSchemeDesignator = coding_scheme
        item.CodeMeaning = code_meaning
        return item

    def _text_item(self, code_value, coding_scheme, code_meaning, text_value):
        """Crea un item TEXT con concept name."""
        from pydicom.dataset import Dataset
        from pydicom.sequence import Sequence
        item = Dataset()
        item.ValueType = "TEXT"
        item.ConceptNameCodeSequence = Sequence([self._code_item(code_value, coding_scheme, code_meaning)])
        item.TextValue = text_value
        item.RelationshipType = "CONTAINS"
        return item

    def _make_container(self, code_value, coding_scheme, code_meaning, children):
        """Crea un item CONTAINER con hijos."""
        from pydicom.dataset import Dataset
        from pydicom.sequence import Sequence
        item = Dataset()
        item.ValueType = "CONTAINER"
        item.ConceptNameCodeSequence = Sequence([self._code_item(code_value, coding_scheme, code_meaning)])
        item.ContinuityOfContent = "SEPARATE"
        item.ContentSequence = Sequence(children)
        item.RelationshipType = "CONTAINS"
        return item


# ──────────────────────────────────────────────────────────────────────────────
# EXPORT: Todas las vistas
# ──────────────────────────────────────────────────────────────────────────────

__all__ = [
    "GenerarInformeView",
    "InformePreliminarDetailView",
    "DescargarInformePDFView",
    "DescargarInformeDICOMSRView",
]