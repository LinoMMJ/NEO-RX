"""
Views para Informes Clínicos — Generación, Firma, Export PDF y DICOM SR.

Endpoints:
- POST   /api/informes/generar/          → Genera borrador automático desde CNN
- GET    /api/informes/                  → Lista paginada de informes (con filtros)
- GET    /api/informes/<pk>/             → Detalle / edición de borrador
- PUT    /api/informes/<pk>/             → Actualiza hallazgos/impresión/recomendaciones
- POST   /api/informes/<pk>/firmar/      → Firma (solo rol=medico)
- GET    /api/informes/<pk>/pdf/         → Export PDF (ReportLab + xhtml2pdf fallback)
- GET    /api/informes/<pk>/dicom-sr/    → Export DICOM SR (Basic Text SR)
"""

from datetime import datetime
from io import BytesIO

from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from django.http import FileResponse
from django.template.loader import render_to_string
from rest_framework.views import APIView
from rest_framework.generics import RetrieveUpdateAPIView, ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from pacientes.models import Estudio
from estudios.models import ImagenDICOM
from diagnostico.models import ResultadoCNN
from .models import InformePreliminar
from .serializers import InformePreliminarSerializer
from neorx.models import log_audit
from neorx.permissions import MedicalWritePermission


# ──────────────────────────────────────────────────────────────────────────────
# GENERADORES DE TEXTO CLÍNICO
# ──────────────────────────────────────────────────────────────────────────────

# NOTA: las claves coinciden EXACTAMENTE con services.PATOLOGIAS_NEUMOLOGIA
# (sin acentos): "Neumonia", "Consolidacion", "Nodulo", "Neumotorax", etc.
# Usar acentos aquí provocaría .get() == 0 y el informe saldría siempre vacío.

def _pct(v):
    return f"{v * 100:.0f}%"


def generar_texto_hallazgos(resultado_cnn, tipo_proyeccion):
    from diagnostico.results import probabilities_es
    probabilities = probabilities_es(resultado_cnn.patologias)
    lines = ["Resultado preliminar de IA; requiere revisión profesional."]
    lines.extend(f"{label}: probabilidad estimada {_pct(value)}."
                 for label, value in sorted(probabilities.items(), key=lambda item: item[1], reverse=True))
    if not probabilities:
        lines.append("Sin probabilidades disponibles; no permite descartar hallazgos.")
    return "\n".join(lines)


def generar_impresion(resultado_cnn):
    return "Resultado preliminar de apoyo a la interpretación. Requiere revisión, validación y firma del médico radiólogo."


def generar_recomendaciones(resultado_cnn):
    return "Conducta y seguimiento según revisión profesional y contexto clínico."


# ──────────────────────────────────────────────────────────────────────────────
# PAGINACIÓN ESTÁNDAR
# ──────────────────────────────────────────────────────────────────────────────

class StandardResultsPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# ──────────────────────────────────────────────────────────────────────────────
# ENDPOINTS: GENERACIÓN, EDICIÓN, FIRMA
# ──────────────────────────────────────────────────────────────────────────────

@method_decorator(ratelimit(key="ip", rate="20/m", block=True), name="post")
class GenerarInformeView(APIView):
    permission_classes = [MedicalWritePermission]

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

        informe, created = InformePreliminar.objects.get_or_create(estudio=estudio)
        if not created:
            return Response(InformePreliminarSerializer(informe, context={"request": request}).data)

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

        # Auditoría: generación/actualización de informe
        log_audit(
            request,
            action="create" if created else "update",
            resource_type="informe",
            resource_id=str(informe.pk),
            after={
                "estudio_id": estudio.pk,
                "estado": informe.estado,
                "medico_id": informe.medico_id if informe.medico else None,
            },
            metadata={"generated_by": request.user.username if request.user.is_authenticated else "system"},
        )

        serializer = InformePreliminarSerializer(informe, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


@method_decorator(ratelimit(key="ip", rate="60/m", block=True), name="get")
@method_decorator(ratelimit(key="ip", rate="20/m", block=True), name="put")
class InformePreliminarDetailView(RetrieveUpdateAPIView):
    queryset = InformePreliminar.objects.select_related('estudio__paciente', 'medico').all()
    serializer_class = InformePreliminarSerializer
    permission_classes = [MedicalWritePermission]

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
        if nuevo_estado == "firmado":
            estudio = serializer.instance.estudio
            estudio.estado = "completado"
            estudio.save(update_fields=["estado"])

        # Auditoría: cambio de estado / firma de informe
        informe = serializer.instance
        log_audit(
            self.request,
            action="update",
            resource_type="informe",
            resource_id=str(informe.pk),
            after={"estado": nuevo_estado, "medico_id": informe.medico_id if informe.medico else None},
        )


class InformeListView(ListAPIView):
    """GET /api/informes/ — Lista paginada de informes con filtros."""
    serializer_class = InformePreliminarSerializer
    permission_classes = [MedicalWritePermission]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['estado', 'medico', 'estudio']
    search_fields = ['estudio__paciente__nombres', 'estudio__paciente__apellidos', 'estudio__paciente__ci', 'hallazgos', 'impresion']
    ordering_fields = ['fecha_creacion', 'fecha_firmado', 'estado']
    ordering = ['-fecha_creacion']

    def get_queryset(self):
        qs = InformePreliminar.objects.select_related('estudio__paciente', 'medico').all()

        # Filtros adicionales via query params
        paciente_id = self.request.query_params.get('paciente')
        if paciente_id:
            qs = qs.filter(estudio__paciente_id=paciente_id)

        fecha_desde = self.request.query_params.get('fecha_desde')
        if fecha_desde:
            qs = qs.filter(fecha_creacion__date__gte=fecha_desde)

        fecha_hasta = self.request.query_params.get('fecha_hasta')
        if fecha_hasta:
            qs = qs.filter(fecha_creacion__date__lte=fecha_hasta)

        medico_id = self.request.query_params.get('medico')
        if medico_id:
            qs = qs.filter(medico_id=medico_id)

        return qs


# ──────────────────────────────────────────────────────────────────────────────
# ENDPOINTS: EXPORT PDF (ReportLab - RF-24)
# ──────────────────────────────────────────────────────────────────────────────

@method_decorator(ratelimit(key="ip", rate="10/m", block=True), name="get")
class DescargarInformePDFView(APIView):
    """
    GET /api/informes/<pk>/pdf/ — genera y descarga el informe como PDF (ReportLab).

    Solo disponible para informes en estado 'firmado'.
    RF-24: ReportLab como motor principal.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            informe = InformePreliminar.objects.select_related(
                "estudio__paciente", "medico"
            ).get(pk=pk)
        except InformePreliminar.DoesNotExist:
            return Response({"error": "Informe no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        if informe.estado != "firmado" or not informe.medico_id or not informe.fecha_firmado:
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

        # Motor principal: ReportLab (RF-24). Fallback: xhtml2pdf (no requiere libs nativas).
        try:
            from .pdf_generator import generar_pdf_informe
            pdf_bytes = generar_pdf_informe(informe, contexto=contexto)
        except Exception as exc:
            # Fallback controlado a xhtml2pdf usando el template HTML existente.
            try:
                from xhtml2pdf import pisa
                html_string = render_to_string("informes/informe_pdf.html", contexto)
                pdf_bytes = BytesIO()
                result = pisa.CreatePDF(html_string, dest=pdf_bytes)
                if result.err:
                    return Response(
                        {"error": "Error al generar el PDF."},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
                pdf_bytes.seek(0)
            except Exception as exc2:
                # Error controlado, sin exponer traceback interno.
                import logging
                logger = logging.getLogger("neorx.request")
                logger.error("PDF generation failed: %s | fallback: %s", exc, exc2)
                return Response(
                    {"error": "No se pudo generar el PDF. Contacte al administrador."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        filename = f"Informe_{paciente.ci}_{informe.estudio.id}.pdf"
        response = FileResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        # Auditoría: descarga de PDF
        log_audit(
            request,
            action="export",
            resource_type="informe",
            resource_id=str(informe.pk),
            after={"formato": "pdf", "filename": filename},
            metadata={"exportado_por": request.user.username if request.user.is_authenticated else "system"},
        )

        return response


# ──────────────────────────────────────────────────────────────────────────────
# ENDPOINTS: EXPORT DICOM SR (Basic Text SR)
# ──────────────────────────────────────────────────────────────────────────────

@method_decorator(ratelimit(key="ip", rate="10/m", block=True), name="get")
class DescargarInformeDICOMSRView(APIView):
    """
    GET /api/informes/<pk>/dicom-sr/ — genera y descarga Structured Report DICOM (Basic Text SR).

    Exportación experimental; conformidad DICOM SR/TID pendiente de validación independiente.
    Incluye: Patient Module, Study Module, SR Document Series/Document Modules,
    y Content Tree con hallazgos, impresión y recomendaciones.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            import pydicom
            from pydicom.uid import (
                generate_uid, ExplicitVRLittleEndian,
                BasicTextSRStorage
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

        if informe.estado != "firmado" or not informe.medico_id or not informe.fecha_firmado:
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
        ds.SOPInstanceUID = ds.file_meta.MediaStorageSOPInstanceUID

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
                self._text_item("113005", "DCM", "Disclaimer", "Este informe es preliminar. Requiere validación y firma del médico radiólogo por el profesional responsable."),
            ]
        )
        root.ContentSequence.append(ai_meta)

        ds.ValueType = root.ValueType
        ds.ConceptNameCodeSequence = root.ConceptNameCodeSequence
        ds.ContinuityOfContent = root.ContinuityOfContent
        ds.ContentSequence = root.ContentSequence
        ds.SpecificCharacterSet = "ISO_IR 192"

        # ───── Save to BytesIO ─────
        from pydicom.filebase import DicomBytesIO
        buffer = DicomBytesIO()
        ds.save_as(buffer, enforce_file_format=True)
        buffer.seek(0)

        filename = f"SR_{paciente.ci}_{informe.estudio.id}.dcm"
        response = FileResponse(buffer, content_type="application/dicom")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        # Auditoría: export DICOM SR
        log_audit(
            request,
            action="export",
            resource_type="informe",
            resource_id=str(informe.pk),
            after={"formato": "dicom-sr", "filename": filename},
            metadata={"exportado_por": request.user.username if request.user.is_authenticated else "system"},
        )

        return response

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
