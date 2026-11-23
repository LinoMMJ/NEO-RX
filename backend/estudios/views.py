import base64
import io
import logging
import time
import uuid

import numpy as np
import pydicom
from PIL import Image as PILImage, ImageOps
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, serializers
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from neorx.models import log_audit
from neorx.permissions import ReceptionUploadPermission
from neorx.validation import clean_plain_text
from diagnostico.results import probabilities_es
from pacientes.models import Estudio, Paciente
from .classification import classify_medical_image
from .models import ImagenDICOM
from .serializers import ImagenDICOMSerializer
from .utils import calcular_borrosidad, detect_projection_type, dicom_pixel_array_2d, dicom_display_pixels, leer_dicom
from .validators import BLUR_THRESHOLD, FileValidationError, validate_file_comprehensive

_IMG_EXTS = ('.png', '.jpg', '.jpeg', '.webp', '.tif', '.tiff', '.bmp')
logger = logging.getLogger(__name__)


class StandardResultsPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def _get_imagen_url(request, imagen):
    """URL privada de la copia PNG o, para registros antiguos, del raster original."""
    if not imagen.archivo_png and imagen.archivo_dicom:
        _ensure_png_preview(imagen)
    if imagen.archivo_png:
        return request.build_absolute_uri(imagen.archivo_png.url) if request else imagen.archivo_png.url
    if imagen.archivo_dicom:
        nombre = imagen.archivo_dicom.name.lower()
        if any(nombre.endswith(ext) for ext in _IMG_EXTS):
            return request.build_absolute_uri(imagen.archivo_dicom.url) if request else imagen.archivo_dicom.url
    return None


def _dicom_a_png(ruta_dcm):
    """Lee DICOM, normaliza pixel array a uint8, retorna (ContentFile, nombre.png)."""
    ds = leer_dicom(ruta_dcm)
    arr_norm = dicom_display_pixels(ds)
    pil_img = PILImage.fromarray(arr_norm)
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG", compress_level=1)
    buf.seek(0)
    return ContentFile(buf.read()), f"{uuid.uuid4().hex}.png"


def _raster_a_png(ruta_imagen):
    """Normaliza un raster válido a PNG para visor, calidad e inferencia."""
    with PILImage.open(ruta_imagen) as source:
        image = ImageOps.exif_transpose(source)
        if image.mode not in {"L", "RGB"}:
            image = image.convert("RGB")
        image.load()
        buf = io.BytesIO()
        # Lossless fast encoding: optimize=True searches compression filters
        # over the full radiograph and delays every upload unnecessarily.
        image.save(buf, format="PNG", compress_level=1)
    buf.seek(0)
    return ContentFile(buf.read()), f"{uuid.uuid4().hex}.png"


def _ensure_png_preview(imagen):
    """Repara bajo demanda registros antiguos que no conservan una vista PNG."""
    if imagen.archivo_png or not imagen.archivo_dicom:
        return bool(imagen.archivo_png)
    try:
        ruta = imagen.archivo_dicom.path
        lower = ruta.lower()
        converter = _dicom_a_png if lower.endswith((".dcm", ".dicom")) else _raster_a_png
        png_content, png_name = converter(ruta)
        imagen.archivo_png.save(png_name, png_content, save=True)
        return True
    except (FileNotFoundError, OSError, ValueError):
        logger.warning("No se pudo reparar la vista PNG de la imagen %s", imagen.pk)
        return False


class DICOMPreviewView(APIView):
    """Convierte un DICOM recibido a una miniatura PNG sin persistirlo.

    Los navegadores no pueden representar archivos .dcm como una imagen. Esta
    ruta se usa exclusivamente antes de confirmar la carga, por lo que no
    crea estudios, imágenes ni archivos en el servidor.
    """

    permission_classes = [ReceptionUploadPermission]

    def post(self, request):
        archivo = request.FILES.get("archivo")
        if not archivo:
            return Response({"error": "Se requiere un archivo DICOM."}, status=status.HTTP_400_BAD_REQUEST)

        nombre = archivo.name.lower()
        if not nombre.endswith((".dcm", ".dicom")):
            return Response({"error": "La vista previa solo está disponible para DICOM."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            validation = validate_file_comprehensive(archivo, file_type="dicom")
            if not validation["valid"]:
                return Response(
                    {"error": "Archivo DICOM inválido", "detalles": validation["errors"]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            dataset = validation["dataset"]
            preview = dicom_display_pixels(dataset)
            image = PILImage.fromarray(preview).convert("L")
            image.thumbnail((768, 768), PILImage.Resampling.LANCZOS)
            buffer = io.BytesIO()
            image.save(buffer, format="PNG", optimize=True)
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
            archivo.seek(0)
            return Response({
                "preview_url": f"data:image/png;base64,{encoded}",
                "width": image.width,
                "height": image.height,
            })
        except Exception:
            archivo.seek(0)
            return Response(
                {"error": "No se pudo leer la imagen DICOM para la vista previa."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class UploadDICOMView(APIView):
    permission_classes = [ReceptionUploadPermission]

    @staticmethod
    def _study_type(classification):
        if classification.classification == "chest_xray":
            return "Radiografía de Tórax"
        region = classification.anatomical_region
        return f"Radiografía de {region}" if region and region != "No determinada" else "Otra radiografía"

    def post(self, request):
        archivo = request.FILES.get("archivo")
        estudio_id = request.data.get("estudio_id")
        paciente_id = request.data.get("paciente_id")
        registro_sin_ia = str(request.data.get("registro_sin_ia", "")).lower() in {"1", "true", "yes"}
        tipo_solicitado = clean_plain_text(
            request.data.get("tipo_estudio") or "",
            max_length=200,
            field_name="tipo de estudio",
        )
        observaciones = clean_plain_text(
            request.data.get("observaciones") or "",
            max_length=5000,
            field_name="observaciones",
            allow_newlines=True,
        )

        if registro_sin_ia and not tipo_solicitado:
            return Response(
                {"error": "Debe especificar el tipo de estudio que se archivará."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not archivo or (not estudio_id and not paciente_id):
            return Response(
                {"error": "Se requiere un archivo y un paciente o estudio válido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        estudio = None
        paciente = None
        if estudio_id:
            try:
                estudio = Estudio.objects.select_related("paciente").get(pk=estudio_id)
                paciente = estudio.paciente
            except (Estudio.DoesNotExist, ValueError, TypeError):
                return Response({"error": "Estudio no encontrado."}, status=status.HTTP_400_BAD_REQUEST)
            if estudio.estado == "completado":
                return Response({"error": "El estudio ya está completado. Cree otro estudio para una nueva imagen."}, status=400)
        else:
            try:
                paciente = Paciente.objects.get(pk=paciente_id)
            except (Paciente.DoesNotExist, ValueError, TypeError):
                return Response({"error": "Paciente no encontrado."}, status=status.HTTP_400_BAD_REQUEST)

        # Validar formato, integridad y contenido antes de crear registros.
        try:
            validation_result = validate_file_comprehensive(archivo, file_type="auto")
        except FileValidationError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if not validation_result["valid"]:
            return Response(
                {"error": "Archivo inválido", "detalles": validation_result["errors"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        classification = classify_medical_image(validation_result)
        classification_data = classification.to_dict()
        if not classification.is_radiograph:
            return Response(
                {
                    "status": "REJECTED",
                    "codigo": "no_radiografia",
                    "error": "La imagen no corresponde a una radiografía válida.",
                    "mensaje": "No se creó ningún estudio ni se almacenó el archivo.",
                    "clasificacion": classification_data,
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        metadata = validation_result.get("metadata", {})
        warnings = validation_result.get("warnings", [])
        archivo.seek(0)

        created_study = False
        if estudio is None:
            tipo_estudio = tipo_solicitado if registro_sin_ia and tipo_solicitado else self._study_type(classification)
            estudio = Estudio.objects.create(
                paciente=paciente,
                fecha=timezone.localdate(),
                tipo_estudio=tipo_estudio,
                observaciones=observaciones,
                estado="registrado" if registro_sin_ia else "pendiente",
            )
            created_study = True
            log_audit(
                request,
                action="create",
                resource_type="estudio",
                resource_id=str(estudio.pk),
                after={
                    "paciente_id": paciente.pk,
                    "tipo_estudio": estudio.tipo_estudio,
                    "estado": estudio.estado,
                },
                metadata={"created_by": request.user.username if request.user.is_authenticated else "system"},
            )
        else:
            new_type = tipo_solicitado if registro_sin_ia and tipo_solicitado else self._study_type(classification)
            if estudio.tipo_estudio != new_type:
                estudio.tipo_estudio = new_type
                estudio.save(update_fields=["tipo_estudio"])

        imagen = None
        try:
            cnn_eligible = classification.cnn_eligible and not registro_sin_ia
            motivo_no_cnn = (
                "Estudio registrado sin análisis por solicitud del usuario."
                if registro_sin_ia else
                ("" if classification.cnn_eligible else classification.reason)
            )
            imagen = ImagenDICOM.objects.create(
                estudio=estudio,
                archivo_dicom=archivo,
                clasificacion_imagen=classification.classification,
                region_anatomica=classification.anatomical_region,
                es_radiografia=classification.is_radiograph,
                apta_para_cnn=cnn_eligible,
                confianza_clasificacion=classification.confidence,
                fuente_clasificacion=classification.source,
                motivo_no_cnn=motivo_no_cnn,
            )
            log_audit(
                request,
                action="create",
                resource_type="imagen_dicom",
                resource_id=str(imagen.pk),
                after={
                    "estudio_id": estudio.pk,
                    "clasificacion": classification.classification,
                    "apta_para_cnn": cnn_eligible,
                },
                metadata={"created_by": request.user.username if request.user.is_authenticated else "system"},
            )

            ruta = imagen.archivo_dicom.path
            ruta_lower = ruta.lower()
            es_dicom = ruta_lower.endswith(".dcm") or ruta_lower.endswith(".dicom")

            try:
                png_content, png_name = _dicom_a_png(ruta) if es_dicom else _raster_a_png(ruta)
                imagen.archivo_png.save(png_name, png_content, save=False)
            except Exception:
                logger.warning("No se pudo generar la copia PNG de la imagen %s", imagen.pk)

            if cnn_eligible:
                proyeccion = detect_projection_type(ruta)
                imagen.tipo_proyeccion = proyeccion["tipo"]
                imagen.proyeccion_fuente = proyeccion["fuente"]
            else:
                proyeccion = None

            ruta_procesable = imagen.archivo_png.path if imagen.archivo_png else ruta
            es_nitida, varianza = calcular_borrosidad(ruta_procesable, umbral=BLUR_THRESHOLD)
            imagen.es_nitida = es_nitida
            imagen.varianza_laplaciana = varianza

            log_audit(
                request,
                action="validate",
                resource_type="imagen_dicom",
                resource_id=str(imagen.pk),
                after={
                    "clasificacion": classification.classification,
                    "region_anatomica": classification.anatomical_region,
                    "apta_para_cnn": cnn_eligible,
                    "es_nitida": es_nitida,
                    "varianza": varianza,
                },
                metadata={
                    "fuente_clasificacion": classification.source,
                    "confianza": classification.confidence,
                },
            )

            # Las radiografías de otras regiones se archivan sin ejecutar la CNN.
            if not cnn_eligible:
                imagen.estado_procesamiento = "sin_analisis"
                imagen.save()
                estudio.estado = "registrado"
                estudio.save(update_fields=["estado"])
                response_data = {
                    "status": "STORED",
                    "mensaje": (
                        "Estudio registrado y vinculado al paciente. No se solicitó análisis con CNN."
                        if registro_sin_ia else
                        "Radiografía almacenada. La CNN está habilitada únicamente para tórax."
                    ),
                    "estudio_id": estudio.pk,
                    "imagen_id": imagen.pk,
                    "clasificacion": classification_data,
                    "es_nitida": es_nitida,
                    "varianza_laplaciana": varianza,
                    "registro_sin_ia": registro_sin_ia,
                }
                url = _get_imagen_url(request, imagen)
                if url:
                    response_data["imagen_png_url"] = url
                if warnings:
                    response_data["advertencias"] = warnings
                return Response(response_data, status=status.HTTP_201_CREATED)

            if not es_nitida:
                estudio.estado = "requiere_repeticion"
                estudio.save(update_fields=["estado"])
                imagen.estado_procesamiento = "sin_analisis"
                imagen.motivo_no_cnn = "Calidad técnica insuficiente por borrosidad."
                imagen.save()
                log_audit(
                    request,
                    action="validate",
                    resource_type="estudio",
                    resource_id=str(estudio.pk),
                    after={"estado": estudio.estado},
                    metadata={"motivo": "calidad técnica insuficiente"},
                )
                response_data = {
                    "status": "STORED",
                    "alerta": "borrosidad",
                    "mensaje": "Radiografía de tórax guardada, pero no se ejecutó la CNN por borrosidad.",
                    "varianza": varianza,
                    "umbral": BLUR_THRESHOLD,
                    "estudio_id": estudio.pk,
                    "imagen_id": imagen.pk,
                    "proyeccion": proyeccion,
                    "clasificacion": classification_data,
                }
                url = _get_imagen_url(request, imagen)
                if url:
                    response_data["imagen_png_url"] = url
                if warnings:
                    response_data["advertencias"] = warnings
                return Response(response_data, status=status.HTTP_200_OK)

            imagen.save()
            estudio.estado = "en_proceso"
            estudio.save(update_fields=["estado"])

            if settings.NEORX_INFERENCE_MODE == "thread":
                from diagnostico.local_queue import enqueue_local_inference
                task_id = enqueue_local_inference(imagen.pk)
                response_data = {
                    "status": "procesando",
                    "mensaje": "Radiografía validada. Análisis CNN en segundo plano.",
                    "estudio_id": estudio.pk,
                    "imagen_id": imagen.pk,
                    "task_id": task_id,
                    "proyeccion": proyeccion,
                    "clasificacion": classification_data,
                }
                url = _get_imagen_url(request, imagen)
                if url:
                    response_data["imagen_png_url"] = url
                if metadata:
                    response_data["metadatos"] = metadata
                return Response(response_data, status=status.HTTP_202_ACCEPTED)

            if settings.NEORX_INFERENCE_MODE == "celery":
                try:
                    from diagnostico.tasks import procesar_imagen_cnn
                    task = procesar_imagen_cnn.apply_async(
                        args=[imagen.pk],
                        soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
                        time_limit=settings.CELERY_TASK_TIME_LIMIT,
                    )
                    response_data = {
                        "status": "procesando",
                        "mensaje": "Radiografía de tórax validada. Análisis CNN en proceso.",
                        "estudio_id": estudio.pk,
                        "imagen_id": imagen.pk,
                        "task_id": task.id,
                        "proyeccion": proyeccion,
                        "clasificacion": classification_data,
                    }
                    url = _get_imagen_url(request, imagen)
                    if url:
                        response_data["imagen_png_url"] = url
                    if metadata:
                        response_data["metadatos"] = metadata
                    return Response(response_data, status=status.HTTP_202_ACCEPTED)
                except Exception:
                    logger.exception("Celery no disponible; se usará inferencia local.")

            from diagnostico.services import DetectorTorax
            from diagnostico.models import ResultadoCNN as ResultadoCNNModel
            from informes.services import create_ai_draft_report

            started = time.time()
            model_result = DetectorTorax.desde_dicom(ruta) if es_dicom else DetectorTorax.desde_png(ruta_procesable)
            inference_time = round(time.time() - started, 3)
            pathologies = probabilities_es(model_result)

            with transaction.atomic():
                cnn_result, _ = ResultadoCNNModel.objects.update_or_create(
                    imagen=imagen,
                    defaults={"patologias": model_result, "tiempo_inferencia_seg": inference_time},
                )
                report, _ = create_ai_draft_report(
                    estudio,
                    imagen,
                    cnn_result,
                    medico=request.user if getattr(request.user, "rol", None) == "medico" else None,
                )
                estudio.estado = "completado"
                estudio.save(update_fields=["estado"])
                imagen.estado_procesamiento = "procesado"
                imagen.save(update_fields=["estado_procesamiento"])

            log_audit(
                request,
                action="process",
                resource_type="imagen_dicom",
                resource_id=str(imagen.pk),
                after={
                    "tiempo_inferencia_seg": inference_time,
                    "n_hallazgos": len(pathologies),
                    "informe_id": report.pk,
                },
                metadata={"modo": "inferencia_local"},
            )

            response_data = {
                "status": "SUCCESS",
                "estudio_id": estudio.pk,
                "imagen_id": imagen.pk,
                "informe_id": report.pk,
                "informe_estado": report.estado,
                "patologias": pathologies,
                "hallazgos": model_result.get("hallazgos", []),
                "advertencias_modelo": model_result.get("advertencias", []),
                "decision": model_result.get("decision", {}),
                "categoria": model_result.get("categoria", {}),
                "enfoque": model_result.get("enfoque"),
                "alcance_modelo": model_result.get("alcance", []),
                "tiempo_inferencia_seg": inference_time,
                "modelo": model_result.get("modelo", "cnn"),
                "es_fine_tuned": bool(model_result.get("es_fine_tuned", False)),
                "resolucion_entrada": DetectorTorax._input_size,
                "thresholds": model_result.get("thresholds", {}),
                "nota_modelo": model_result.get("nota", ""),
                "es_nitida": imagen.es_nitida,
                "varianza_laplaciana": imagen.varianza_laplaciana,
                "proyeccion": proyeccion,
                "clasificacion": classification_data,
            }
            if warnings:
                response_data["advertencias"] = warnings
            if metadata:
                response_data["metadatos"] = metadata
            url = _get_imagen_url(request, imagen)
            if url:
                response_data["imagen_png_url"] = url
            return Response(response_data, status=status.HTTP_200_OK)

        except FileValidationError as exc:
            if imagen is not None:
                imagen.estado_procesamiento = "error"
                imagen.save(update_fields=["estado_procesamiento"])
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception("Error procesando imagen del estudio %s", estudio.pk)
            if imagen is not None:
                imagen.estado_procesamiento = "error"
                imagen.save(update_fields=["estado_procesamiento"])
            estudio.estado = "pendiente"
            estudio.save(update_fields=["estado"])
            return Response(
                {
                    "error": (
                        "La radiografía se guardó, pero no pudo completarse el procesamiento."
                        if imagen else "No se pudo guardar la radiografía. Verifique el almacenamiento del servidor."
                    ),
                    "detalles": ["Contacte al administrador para revisar el modelo y el almacenamiento del servidor."],
                    "estudio_id": estudio.pk,
                    "imagen_id": imagen.pk if imagen else None,
                    "estudio_creado": created_study,
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )


class ImageListFilters(serializers.Serializer):
    estudio = serializers.IntegerField(min_value=1, required=False)
    paciente = serializers.IntegerField(min_value=1, required=False)
    fecha_desde = serializers.DateField(required=False)
    fecha_hasta = serializers.DateField(required=False)

    def validate(self, attrs):
        if attrs.get("fecha_desde") and attrs.get("fecha_hasta") and attrs["fecha_desde"] > attrs["fecha_hasta"]:
            raise serializers.ValidationError("La fecha inicial no puede ser posterior a la final.")
        return attrs


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
        filters = ImageListFilters(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        params = filters.validated_data
        qs = ImagenDICOM.objects.select_related('estudio__paciente').all()
        estudio_id = params.get('estudio')
        if estudio_id:
            qs = qs.filter(estudio_id=estudio_id)
        paciente_id = params.get('paciente')
        if paciente_id:
            qs = qs.filter(estudio__paciente_id=paciente_id)
        fecha_desde = params.get('fecha_desde')
        if fecha_desde:
            qs = qs.filter(fecha_subida__date__gte=fecha_desde)
        fecha_hasta = params.get('fecha_hasta')
        if fecha_hasta:
            qs = qs.filter(fecha_subida__date__lte=fecha_hasta)
        return qs


class ObtenerEstadoTareaView(APIView):
    """GET /api/estudios/tarea/<task_id>/ — el frontend hace polling aquí."""
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        if task_id.startswith("local-"):
            try:
                imagen_id = int(task_id.removeprefix("local-"))
                imagen = ImagenDICOM.objects.select_related("estudio").get(pk=imagen_id)
            except (ValueError, ImagenDICOM.DoesNotExist):
                return Response({"status": "FAILURE", "error": "Tarea local no encontrada."}, status=404)
            if imagen.estado_procesamiento == "error":
                return Response({"status": "FAILURE", "error": "No se pudo procesar la imagen."}, status=500)
            if imagen.estado_procesamiento == "sin_analisis":
                return Response({"status": "STORED", "imagen_id": imagen.pk,
                                 "estudio_id": imagen.estudio_id,
                                 "mensaje": imagen.motivo_no_cnn or "Radiografía guardada sin análisis CNN."})
            if imagen.estado_procesamiento != "procesado":
                return Response({"status": "STARTED", "mensaje": "Procesando con CNN..."})
            from diagnostico.models import ResultadoCNN
            try:
                res_cnn = ResultadoCNN.objects.get(imagen=imagen)
            except ResultadoCNN.DoesNotExist:
                return Response({"status": "STARTED", "mensaje": "Guardando resultado..."})
            report = getattr(imagen.estudio, "informe", None)
            datos = {
                "status": "SUCCESS", "estudio_id": imagen.estudio_id, "imagen_id": imagen.pk,
                "informe_id": report.pk if report else None,
                "informe_estado": report.estado if report else None,
                "patologias": probabilities_es(res_cnn.patologias),
                "hallazgos": res_cnn.patologias.get("hallazgos", []),
                "advertencias_modelo": res_cnn.patologias.get("advertencias", []),
                "decision": res_cnn.patologias.get("decision", {}),
                "categoria": res_cnn.patologias.get("categoria", {}),
                "enfoque": res_cnn.patologias.get("enfoque"),
                "alcance_modelo": res_cnn.patologias.get("alcance", []),
                "tiempo_inferencia_seg": res_cnn.tiempo_inferencia_seg,
                "modelo": res_cnn.patologias.get("modelo", "cnn"),
                "es_fine_tuned": bool(res_cnn.patologias.get("es_fine_tuned", False)),
                "resolucion_entrada": res_cnn.patologias.get("resolucion_entrada"),
                "es_nitida": imagen.es_nitida, "varianza_laplaciana": imagen.varianza_laplaciana,
            }
            url = _get_imagen_url(request, imagen)
            if url:
                datos["imagen_png_url"] = url
            if imagen.tipo_proyeccion:
                datos["proyeccion"] = {"tipo": imagen.tipo_proyeccion, "fuente": imagen.proyeccion_fuente}
            return Response(datos)

        from celery.result import AsyncResult

        try:
            uuid.UUID(task_id)
        except (ValueError, TypeError):
            return Response({"error": "Identificador de tarea inválido."}, status=400)
        try:
            resultado = AsyncResult(task_id)
            state = resultado.state
        except Exception:
            logger.exception("No se pudo consultar el servicio de tareas")
            return Response({"error": "El servicio de tareas no está disponible. El estudio se conserva."}, status=503)

        if state in ('PENDING', 'STARTED', 'RETRY'):
            return Response({"status": state, "mensaje": "Procesando con CNN..."})

        if state == 'SUCCESS':
            datos = resultado.result or {}
            if datos.get("status") == "STORED":
                return Response(datos)
            imagen_id = datos.get('imagen_id')
            try:
                from diagnostico.models import ResultadoCNN
                imagen = ImagenDICOM.objects.get(pk=imagen_id)
                res_cnn = ResultadoCNN.objects.get(imagen=imagen)
                resp = {
                    "status": "SUCCESS",
                    "estudio_id": imagen.estudio_id,
                    "imagen_id": imagen.pk,
                    "informe_id": datos.get("informe_id"),
                    "informe_estado": datos.get("informe_estado"),
                    "patologias": probabilities_es(res_cnn.patologias),
                    "hallazgos": res_cnn.patologias.get("hallazgos", []),
                    "advertencias_modelo": res_cnn.patologias.get("advertencias", []),
                    "decision": res_cnn.patologias.get("decision", {}),
                    "categoria": res_cnn.patologias.get("categoria", {}),
                    "enfoque": res_cnn.patologias.get("enfoque"),
                    "alcance_modelo": res_cnn.patologias.get("alcance", []),
                    "tiempo_inferencia_seg": res_cnn.tiempo_inferencia_seg,
                    "modelo": datos.get("modelo", "cnn"),
                    "es_fine_tuned": bool(datos.get("es_fine_tuned", False)),
                    "resolucion_entrada": datos.get("resolucion_entrada"),
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


class RetryImageView(APIView):
    """Retry a saved failed image without creating another study or file."""
    permission_classes = [ReceptionUploadPermission]

    def post(self, request, pk):
        with transaction.atomic():
            try:
                imagen = ImagenDICOM.objects.select_for_update().select_related('estudio').get(pk=pk)
            except ImagenDICOM.DoesNotExist:
                return Response({'error': 'Imagen no encontrada.'}, status=404)
            if imagen.estado_procesamiento != 'error':
                return Response({'error': 'Solo puede reintentarse un análisis fallido.'}, status=409)
            report = getattr(imagen.estudio, 'informe', None)
            if report and report.estado == 'firmado':
                return Response({'error': 'El estudio tiene un informe firmado y no puede reprocesarse.'}, status=409)
            if not imagen.apta_para_cnn or imagen.clasificacion_imagen != 'chest_xray' or imagen.es_nitida is not True:
                return Response({'error': 'La imagen no cumple los requisitos para el análisis CNN.'}, status=400)
            if not imagen.archivo_dicom or not imagen.archivo_dicom.storage.exists(imagen.archivo_dicom.name):
                return Response({'error': 'El archivo original no está disponible. Restaure el archivo antes de reintentar.'}, status=409)
            imagen.estado_procesamiento = 'pendiente'
            imagen.save(update_fields=['estado_procesamiento'])
            imagen.estudio.estado = 'en_proceso'
            imagen.estudio.save(update_fields=['estado'])
        try:
            if settings.NEORX_INFERENCE_MODE == 'celery':
                from diagnostico.tasks import procesar_imagen_cnn
                task_id = procesar_imagen_cnn.delay(imagen.pk).id
            else:
                from diagnostico.local_queue import enqueue_local_inference
                task_id = enqueue_local_inference(imagen.pk)
        except Exception:
            ImagenDICOM.objects.filter(pk=pk).update(estado_procesamiento='error')
            Estudio.objects.filter(pk=imagen.estudio_id).update(estado='pendiente')
            logger.exception('No se pudo reencolar la imagen %s', pk)
            return Response({'error': 'No se pudo iniciar el análisis. La imagen permanece guardada.'}, status=503)
        log_audit(request, action='process', resource_type='imagen_dicom', resource_id=str(pk), metadata={'modo': 'reintento'})
        return Response({'status': 'procesando', 'task_id': task_id, 'imagen_id': pk, 'estudio_id': imagen.estudio_id}, status=202)


class ImagenDICOMDetailView(RetrieveAPIView):
    queryset = ImagenDICOM.objects.select_related('estudio__paciente').all()
    serializer_class = ImagenDICOMSerializer
    permission_classes = [IsAuthenticated]
