import os
import hashlib
import time
import logging

import numpy as np
import pydicom
from PIL import Image as PILImage

from django.conf import settings
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from django.core.cache import cache
from rest_framework.generics import RetrieveAPIView
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from estudios.models import ImagenDICOM
from .models import ResultadoCNN
from .serializers import ResultadoCNNSerializer
from .services import DetectorTorax, PATOLOGIAS_NEUMOLOGIA_BASELINE as PATOLOGIAS_NEUMOLOGIA
from neorx.models import log_audit
from .results import probabilities_es

logger = logging.getLogger(__name__)


@method_decorator(ratelimit(key="ip", rate="60/m", block=True), name="get")
class ResultadoCNNView(RetrieveAPIView):
    serializer_class = ResultadoCNNSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        imagen_id = self.kwargs["imagen_id"]
        return ResultadoCNN.objects.select_related("imagen").get(imagen_id=imagen_id)

    def retrieve(self, request, *args, **kwargs):
        imagen_id = self.kwargs["imagen_id"]
        try:
            instance = self.get_object()
        except ResultadoCNN.DoesNotExist:
            try:
                img = ImagenDICOM.objects.get(pk=imagen_id)
                from estudios.views import _get_imagen_url
                data = {
                    "imagen_id": img.pk,
                    "estudio_id": img.estudio_id,
                    "estado_procesamiento": img.estado_procesamiento,
                    "clasificacion_imagen": img.clasificacion_imagen,
                    "region_anatomica": img.region_anatomica,
                    "apta_para_cnn": img.apta_para_cnn,
                    "confianza_clasificacion": img.confianza_clasificacion,
                    "fuente_clasificacion": img.fuente_clasificacion,
                    "motivo_no_cnn": img.motivo_no_cnn,
                    "es_nitida": img.es_nitida,
                    "varianza_laplaciana": img.varianza_laplaciana,
                }
                url = _get_imagen_url(request, img)
                if url:
                    data["imagen_png_url"] = url
                return Response(data, status=status.HTTP_200_OK)
            except ImagenDICOM.DoesNotExist:
                return Response({"error": "Imagen no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        imagen = instance.imagen
        from estudios.views import _get_imagen_url
        data = self.get_serializer(instance).data
        data["imagen_id"] = imagen.pk
        data["estado_procesamiento"] = imagen.estado_procesamiento
        data["es_nitida"] = imagen.es_nitida
        data["varianza_laplaciana"] = imagen.varianza_laplaciana
        url = _get_imagen_url(request, imagen)
        if url:
            data["imagen_png_url"] = url
        # Preserve acquisition-time metadata; current environment cannot
        # describe an older result generated with other weights/resolution.
        metadata = instance.patologias
        data["modelo"] = metadata.get("modelo", "Modelo histórico")
        data["es_fine_tuned"] = metadata.get("es_fine_tuned")
        data["resolucion_entrada"] = metadata.get("resolucion_entrada")
        data["thresholds"] = metadata.get("thresholds", {})
        if "resolucion_entrada" not in metadata:
            data["advertencias_modelo"] = [*data["advertencias_modelo"], "Resultado histórico sin resolución ni umbrales conservados. Los cambios actuales no recalculan este estudio."]
        if imagen.tipo_proyeccion:
            data["proyeccion"] = {
                "tipo": imagen.tipo_proyeccion,
                "fuente": imagen.proyeccion_fuente,
            }

        return Response(data)


@method_decorator(ratelimit(key="ip", rate="30/m", block=True), name="get")
class GradCAMView(APIView):
    """
    GET /api/diagnostico/gradcam/?imagen_id=X&pathology=Pneumonia

    Genera el mapa de calor Grad-CAM para la imagen y la patología indicadas.
    Si no se pasa pathology, usa la de mayor probabilidad en ResultadoCNN.
    """
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _cache_key(imagen, pathology_en):
        """Clave versionada: invalida mapas si se reemplaza el checkpoint."""
        checkpoint = os.environ.get("NEORX_MODEL_PATH", "baseline")
        try:
            revision = str(os.stat(checkpoint).st_mtime_ns) if checkpoint != "baseline" else os.environ.get("NEORX_BASELINE_WEIGHTS", "baseline")
        except OSError:
            revision = checkpoint
        raw = f"gradcam-v4:{imagen.pk}:{imagen.archivo_dicom.name}:{pathology_en}:{revision}:{DetectorTorax._finetuned_input_size()}"
        return "gradcam:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, request):
        imagen_id = request.query_params.get("imagen_id")
        pathology_en = request.query_params.get("pathology")  # nombre en inglés (e.g. "Pneumonia")

        if not imagen_id:
            return Response({"error": "Se requiere 'imagen_id'."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            imagen = ImagenDICOM.objects.select_related("resultado_cnn").get(pk=imagen_id)
        except (ImagenDICOM.DoesNotExist, ValueError, TypeError):
            return Response({"error": "Imagen no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        try:
            resultado = getattr(imagen, "resultado_cnn", None)
            if resultado is None:
                return Response({"error": "El mapa requiere un análisis CNN completado."}, status=status.HTTP_409_CONFLICT)
            previous_size = resultado.patologias.get("resolucion_entrada")
            if previous_size and previous_size != DetectorTorax._finetuned_input_size():
                return Response({"error": "Este resultado se calculó con otra resolución. Realice un nuevo análisis antes de interpretar el mapa."}, status=status.HTTP_409_CONFLICT)

            # Si no se especificó patología, usar la de mayor probabilidad
            if not pathology_en:
                if resultado and resultado.patologias:
                    scores = probabilities_es(resultado.patologias)
                    top_es = max(scores, key=scores.get) if scores else None
                    # Invertir el mapa español → inglés
                    pathology_en = next(
                        (k for k, v in PATOLOGIAS_NEUMOLOGIA.items() if v == top_es), None
                    )
                if not pathology_en:
                    return Response(
                        {"error": "No se encontró patología de referencia."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            cache_key = self._cache_key(imagen, pathology_en)
            cached = cache.get(cache_key)
            if cached:
                return Response({**cached, "cache": True})

            modelo = DetectorTorax.cargar()

            if pathology_en not in list(modelo.pathologies):
                return Response(
                    {"error": f"Patología '{pathology_en}' no reconocida por el modelo."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            indice_clase = list(modelo.pathologies).index(pathology_en)

            started = time.perf_counter()
            # Leer datos de la imagen
            ruta = imagen.archivo_dicom.path
            ruta_lower = ruta.lower()

            if ruta_lower.endswith(".dcm") or ruta_lower.endswith(".dicom"):
                from estudios.utils import dicom_display_pixels, leer_dicom
                ds = leer_dicom(ruta)
                arr = dicom_display_pixels(ds).astype(np.float32)
                maxval = 255.0
            else:
                arr = np.array(PILImage.open(ruta).convert("L")).astype(np.float32)
                maxval = 255.0

            tensor = DetectorTorax._preprocesar(arr, maxval)

            from .gradcam import GeneradorGradCAM
            # Calcular cam UNA VEZ y reutilizar en ambos overlays
            # Reuse cached features for the linear ResNet head. Serialize the
            # fallback forward pass with inference to avoid CPU contention.
            with DetectorTorax._inference_lock:
                # Another request may have completed while this one waited.
                cached = cache.get(cache_key)
                if cached:
                    return Response({**cached, "cache": True})
                cam = GeneradorGradCAM.calcular(modelo, tensor, indice_clase)
                centroide = GeneradorGradCAM.get_centroide(cam)
                overlay = GeneradorGradCAM.overlay_base64(modelo, tensor, indice_clase, arr, cam=cam)
                solo_calor = GeneradorGradCAM.overlay_solo_heatmap_base64(
                    modelo, tensor, indice_clase, cam=cam
                )

            # Auditoría: generación de Grad-CAM
            payload = {
                "overlay": overlay,
                "solo_calor": solo_calor,
                "patologia": pathology_en,
                "activacion_maxima": round(float(cam.max()), 4),
                "centroide": centroide,
                "cache": False,
                "tiempo_generacion_ms": round((time.perf_counter() - started) * 1000),
            }
            cache.set(cache_key, payload, timeout=getattr(settings, "GRADCAM_CACHE_TIMEOUT", 60 * 60 * 12))

            log_audit(
                request,
                action="gradcam",
                resource_type="imagen_dicom",
                resource_id=str(imagen.pk),
                metadata={
                    "patologia": pathology_en,
                    "indice_clase": indice_clase,
                },
            )

            return Response(payload)

        except Exception as exc:
            logger.exception("Error generando Grad-CAM de imagen %s", imagen_id)
            return Response({"error": "No se pudo generar la visualización. La radiografía y su resultado se conservan; puede reintentar."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
