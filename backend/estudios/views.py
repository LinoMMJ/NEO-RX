import io
import time
import uuid

import numpy as np
import pydicom as _pydicom
from PIL import Image as PILImage
from django.core.files.base import ContentFile
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from neorx.models import log_audit
from neorx.permissions import ReceptionUploadPermission
from diagnostico.results import probabilities_es
from pacientes.models import Estudio
from .models import ImagenDICOM
from .serializers import ImagenDICOMSerializer
from .utils import calcular_borrosidad, detect_projection_type
from .validators import BLUR_THRESHOLD, FileValidationError, validate_file_comprehensive

_IMG_EXTS = ('.png', '.jpg', '.jpeg', '.webp')


class StandardResultsPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def _get_imagen_url(request, imagen):
    """URL de previsualización: PNG convertido (DICOM) o el archivo original (PNG/JPG)."""
    if imagen.archivo_png:
        return request.build_absolute_uri(imagen.archivo_png.url)
    if imagen.archivo_dicom:
        nombre = imagen.archivo_dicom.name.lower()
        if any(nombre.endswith(ext) for ext in _IMG_EXTS):
            return request.build_absolute_uri(imagen.archivo_dicom.url)
    return None


def _dicom_a_png(ruta_dcm):
    """Lee DICOM, normaliza pixel array a uint8, retorna (ContentFile, nombre.png)."""
    ds = _pydicom.dcmread(ruta_dcm)
    arr = ds.pixel_array.astype(np.float32)
    if getattr(ds, "PhotometricInterpretation", "") == "MONOCHROME1":
        arr = arr.max() - arr
    if arr.ndim > 2:
        arr = arr[:, :, 0]
    arr_norm = ((arr - arr.min()) / (arr.max() - arr.min() + 1e-8) * 255).astype(np.uint8)
    pil_img = PILImage.fromarray(arr_norm)
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    buf.seek(0)
    return ContentFile(buf.read()), f"{uuid.uuid4().hex}.png"


class UploadDICOMView(APIView):
    permission_classes = [ReceptionUploadPermission]

    def post(self, request):
        archivo = request.FILES.get("archivo")
        estudio_id = request.data.get("estudio_id")

        if not archivo or not estudio_id:
            return Response(
                {"error": "Se requieren los campos 'archivo' y 'estudio_id'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            estudio = Estudio.objects.get(pk=estudio_id)
        except Estudio.DoesNotExist:
            return Response({"error": "Estudio no encontrado."}, status=status.HTTP_400_BAD_REQUEST)

        if estudio.estado == "completado":
            return Response({"error": "El estudio ya tiene un informe firmado."}, status=400)

        # ─── VALIDACIÓN ROBUSTA DEL ARCHIVO (antes de guardar en BD) ───
        try:
            validation_result = validate_file_comprehensive(archivo, file_type='auto')
        except FileValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if not validation_result['valid']:
            return Response(
                {"error": "Archivo inválido", "detalles": validation_result['errors']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        metadata = validation_result.get('metadata', {})
        warnings = validation_result.get('warnings', [])

        imagen = None
        try:
            imagen = ImagenDICOM.objects.create(estudio=estudio, archivo_dicom=archivo)
            log_audit(
                request,
                action="create",
                resource_type="imagen_dicom",
                resource_id=str(imagen.pk),
                after={"estudio_id": estudio.pk},
                metadata={"created_by": request.user.username if request.user.is_authenticated else "system"},
            )

            ruta = imagen.archivo_dicom.path
            ruta_lower = ruta.lower()
            es_dicom = ruta_lower.endswith(".dcm") or ruta_lower.endswith(".dicom")

            # Convertir DICOM → PNG para visualización (best-effort, no bloquea)
            if es_dicom:
                try:
                    png_content, png_name = _dicom_a_png(ruta)
                    imagen.archivo_png.save(png_name, png_content, save=False)
                except Exception:
                    pass

            # Detección automática del tipo de proyección (PA / AP / LAT)
            proyeccion = detect_projection_type(ruta)
            imagen.tipo_proyeccion = proyeccion["tipo"]
            imagen.proyeccion_fuente = proyeccion["fuente"]

            # Verificación de borrosidad
            es_nitida, varianza = calcular_borrosidad(ruta, umbral=BLUR_THRESHOLD)
            imagen.es_nitida = es_nitida
            imagen.varianza_laplaciana = varianza

            log_audit(
                request,
                action="validate",
                resource_type="imagen_dicom",
                resource_id=str(imagen.pk),
                after={"es_nitida": es_nitida, "varianza": varianza},
                metadata={"umbral": BLUR_THRESHOLD, "proyeccion": proyeccion.get("tipo")},
            )

            if not es_nitida:
                estudio.estado = "requiere_repeticion"
                estudio.save(update_fields=["estado"])
                log_audit(request, action="validate", resource_type="estudio", resource_id=str(estudio.pk),
                          after={"estado": estudio.estado}, metadata={"motivo": "calidad técnica insuficiente"})
                imagen.estado_procesamiento = "procesado"
                imagen.save()
                resp = {
                    "alerta": "borrosidad",
                    "varianza": varianza,
                    "umbral": BLUR_THRESHOLD,
                    "imagen_id": imagen.pk,
                    "proyeccion": proyeccion,
                }
                url = _get_imagen_url(request, imagen)
                if url:
                    resp["imagen_png_url"] = url
                if warnings:
                    resp["advertencias"] = warnings
                return Response(resp, status=status.HTTP_200_OK)

            imagen.save()

            # Intenta despachar a Celery; si no hay broker ejecuta en proceso
            celery_ok = False
            try:
                from diagnostico.tasks import procesar_imagen_cnn
                task = procesar_imagen_cnn.delay(imagen.pk)
                celery_ok = True
                resp = {
                    "status": "procesando",
                    "mensaje": "Imagen recibida. Análisis CNN en proceso.",
                    "imagen_id": imagen.pk,
                    "task_id": task.id,
                    "proyeccion": proyeccion,
                }
                url = _get_imagen_url(request, imagen)
                if url:
                    resp["imagen_png_url"] = url
                if metadata:
                    resp["metadatos"] = metadata
                return Response(resp, status=status.HTTP_202_ACCEPTED)
            except Exception:
                pass

            if not celery_ok:
                from diagnostico.services import DetectorTorax
                from diagnostico.models import ResultadoCNN as ResultadoCNNModel

                t0 = time.time()
                patologias = DetectorTorax.desde_dicom(ruta) if es_dicom else DetectorTorax.desde_png(ruta)
                tiempo = round(time.time() - t0, 3)

                ResultadoCNNModel.objects.update_or_create(
                    imagen=imagen,
                    defaults={"patologias": probabilities_es(patologias), "tiempo_inferencia_seg": tiempo},
                )
                imagen.estado_procesamiento = "procesado"
                imagen.save()

                log_audit(
                    request,
                    action="process",
                    resource_type="imagen_dicom",
                    resource_id=str(imagen.pk),
                    after={
                        "tiempo_inferencia_seg": tiempo,
                        "n_hallazgos": len(patologias) if isinstance(patologias, dict) else 0,
                    },
                    metadata={"modo": "inferencia_local"},
                )

                resp = {
                    "status": "SUCCESS",
                    "imagen_id": imagen.pk,
                    "patologias": patologias,
                    "tiempo_inferencia_seg": tiempo,
                    "es_nitida": imagen.es_nitida,
                    "varianza_laplaciana": imagen.varianza_laplaciana,
                    "proyeccion": proyeccion,
                }
                if warnings:
                    resp["advertencias"] = warnings
                if metadata:
                    resp["metadatos"] = metadata
                url = _get_imagen_url(request, imagen)
                if url:
                    resp["imagen_png_url"] = url
                return Response(resp, status=status.HTTP_200_OK)

        except FileValidationError as e:
            if imagen is not None:
                imagen.estado_procesamiento = "error"
                imagen.save()
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            if imagen is not None:
                imagen.estado_procesamiento = "error"
                imagen.save()
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class ImagenDICOMListView(ListAPIView):
    """GET /api/estudios/imagenes/ — Lista paginada de imágenes con filtros."""
    serializer_class = ImagenDICOMSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['estado_procesamiento', 'tipo_proyeccion', 'es_nitida', 'estudio']
    search_fields = ['estudio__paciente__nombres', 'estudio__paciente__apellidos', 'estudio__paciente__ci']
    ordering_fields = ['fecha_subida', 'varianza_laplaciana']
    ordering = ['-fecha_subida']

    def get_queryset(self):
        qs = ImagenDICOM.objects.select_related('estudio__paciente').all()
        estudio_id = self.request.query_params.get('estudio')
        if estudio_id:
            qs = qs.filter(estudio_id=estudio_id)
        paciente_id = self.request.query_params.get('paciente')
        if paciente_id:
            qs = qs.filter(estudio__paciente_id=paciente_id)
        fecha_desde = self.request.query_params.get('fecha_desde')
        if fecha_desde:
            qs = qs.filter(fecha_subida__date__gte=fecha_desde)
        fecha_hasta = self.request.query_params.get('fecha_hasta')
        if fecha_hasta:
            qs = qs.filter(fecha_subida__date__lte=fecha_hasta)
        return qs


class ObtenerEstadoTareaView(APIView):
    """GET /api/estudios/tarea/<task_id>/ — el frontend hace polling aquí."""
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        from celery.result import AsyncResult

        resultado = AsyncResult(task_id)
        state = resultado.state

        if state in ('PENDING', 'STARTED', 'RETRY'):
            return Response({"status": state, "mensaje": "Procesando con CNN..."})

        if state == 'SUCCESS':
            datos = resultado.result or {}
            imagen_id = datos.get('imagen_id')
            try:
                from diagnostico.models import ResultadoCNN
                imagen = ImagenDICOM.objects.get(pk=imagen_id)
                res_cnn = ResultadoCNN.objects.get(imagen=imagen)
                resp = {
                    "status": "SUCCESS",
                    "imagen_id": imagen.pk,
                    "patologias": res_cnn.patologias,
                    "tiempo_inferencia_seg": res_cnn.tiempo_inferencia_seg,
                    "es_nitida": imagen.es_nitida,
                    "varianza_laplaciana": imagen.varianza_laplaciana,
                }
                url = _get_imagen_url(request, imagen)
                if url:
                    resp["imagen_png_url"] = url
                if imagen.tipo_proyeccion:
                    resp["proyeccion"] = {
                        "tipo": imagen.tipo_proyeccion,
                        "fuente": imagen.proyeccion_fuente,
                    }
                return Response(resp)
            except Exception:
                return Response({"status": "SUCCESS", "resultado": datos})

        if state == 'FAILURE':
            return Response(
                {"status": "FAILURE", "error": "No se pudo procesar la imagen. Contacte al administrador."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({"status": state})


class ImagenDICOMDetailView(RetrieveAPIView):
    queryset = ImagenDICOM.objects.select_related('estudio__paciente').all()
    serializer_class = ImagenDICOMSerializer
    permission_classes = [IsAuthenticated]
